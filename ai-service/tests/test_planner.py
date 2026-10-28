import random
from datetime import timedelta
from itertools import combinations

from app.planner import DETAIL_DAYS, HORIZON_DAYS, make_plan
from app.schemas import WEEKDAYS
from tests.factories import SUNDAY, request, task


def day(offset: int) -> str:
    return (SUNDAY + timedelta(days=offset)).isoformat()


def assessed(plan) -> dict[int, dict]:
    return {t.task_id: t.model_dump() for t in plan.tasks}


def hours_by_day(plan, task_id: int) -> list[float]:
    return [sum(b.hours for b in d.blocks if b.task_id == task_id) for d in plan.days]


def test_one_task_is_planned_from_the_first_day():
    # Due Wednesday: Sunday to Tuesday are usable, 2 h each.
    plan = make_plan(request([task(1, day(3), 3)]))

    assert hours_by_day(plan, 1) == [2, 1, 0, 0, 0, 0, 0]
    assert assessed(plan)[1] == {
        "task_id": 1,
        "assessment": "on_track",
        "needed_hours": 3,
        "free_hours_before_due": 6,
        "slack_hours": 3,
        "planned_hours": 3,
        "planned_hours_this_week": 3,
        "missing_hours": 0,
    }
    assert plan.all_fit
    assert plan.source == "baseline"


def test_the_plan_shows_seven_days_and_looks_eight_weeks_ahead():
    plan = make_plan(request([]))

    assert [d.date for d in plan.days] == [
        SUNDAY + timedelta(days=i) for i in range(DETAIL_DAYS)
    ]
    assert plan.horizon_end == SUNDAY + timedelta(days=HORIZON_DAYS - 1)
    assert plan.tasks == []
    assert plan.all_fit


def test_estimates_are_rounded_up_to_half_hours():
    plan = make_plan(request([task(1, day(5), 1.2)]))

    assert assessed(plan)[1]["needed_hours"] == 1.5
    assert hours_by_day(plan, 1)[0] == 1.5


def test_free_hours_follow_the_weekdays_and_blocked_dates():
    weekly = dict.fromkeys(WEEKDAYS, 3) | {"monday": 0, "friday": 1.5}
    plan = make_plan(
        request(
            [task(1, day(20), 40)],
            weekly_hours=weekly,
            blocked_dates=[day(2), day(30)],  # Tuesday, and a day after this week
        )
    )

    # Sunday 3, Monday 0, Tuesday blocked, Wednesday 3, Thursday 3, Friday 1.5
    assert [d.free_hours for d in plan.days] == [3, 0, 0, 3, 3, 1.5, 3]
    assert [d.planned_hours for d in plan.days] == [3, 0, 0, 3, 3, 1.5, 3]


def test_work_stops_the_day_before_the_due_date():
    # An exam on Tuesday morning: only Sunday and Monday are left to study.
    exam = task(1, f"{day(2)}T09:00", 10, type="exam")
    plan = make_plan(request([exam]))

    assert hours_by_day(plan, 1) == [2, 2, 0, 0, 0, 0, 0]
    assert assessed(plan)[1]["missing_hours"] == 6


def test_least_slack_comes_first_not_the_earliest_due_date():
    # Short, due Monday: 3 free hours before it, needs 1, so slack 2.
    # Long, due Tuesday: 6 free hours before it, needs 5, so slack 1.
    # Giving Sunday to either task alone would make the other one late.
    plan = make_plan(request([task(1, day(1), 1), task(2, day(2), 5)], every_day=3))

    assert [t.task_id for t in plan.tasks] == [2, 1]  # least slack first
    assert all(t.assessment == "on_track" for t in plan.tasks)
    assert hours_by_day(plan, 1)[:2] == [1, 0]
    assert hours_by_day(plan, 2)[:2] == [2, 3]


def test_a_tight_task_due_later_gets_the_first_days():
    # Short, due Thursday: 8 free hours before it, needs 1 (slack 7).
    # Long, due Friday: 10 free hours before it, needs 9 (slack 1).
    # The earliest due date would start with the short task; slack starts with
    # the long one, and the short one still gets its hour in time.
    plan = make_plan(request([task(1, day(4), 1), task(2, day(5), 9)]))

    assert hours_by_day(plan, 2) == [2, 2, 2, 1, 2, 0, 0]
    assert hours_by_day(plan, 1) == [0, 0, 0, 1, 0, 0, 0]
    assert plan.all_fit


def test_when_not_everything_fits_the_most_tasks_stay_on_time():
    # 3 h a day. The big task cannot fit, and putting it first would make
    # both small tasks late as well. It gets the hours that are left.
    small_monday = task(1, day(1), 2)
    small_tuesday = task(2, day(2), 2)
    big = task(3, day(3), 10)
    plan = make_plan(request([small_monday, small_tuesday, big], every_day=3))
    tasks = assessed(plan)

    assert tasks[1]["assessment"] == tasks[2]["assessment"] == "on_track"
    assert tasks[3]["assessment"] == "shortfall"
    assert tasks[3]["planned_hours"] == 5  # 9 free hours before Wednesday, minus 4
    assert tasks[3]["missing_hours"] == 5
    assert tasks[3]["slack_hours"] == -1
    assert not plan.all_fit


def test_tasks_the_plan_cannot_schedule_are_reported():
    tasks = [
        task(1, day(4), None),  # no estimate
        task(2, day(-1), 3),  # due yesterday
        task(3, day(HORIZON_DAYS + 1), 3),  # after the horizon
        task(4, f"{day(0)}T20:00", 1),  # due today: no day before it is left
    ]
    plan = make_plan(request(tasks))
    result = assessed(plan)

    assert result[1]["assessment"] == "no_estimate"
    assert result[1]["needed_hours"] is None
    assert result[2]["assessment"] == "overdue"
    assert result[3]["assessment"] == "later"
    assert result[4]["assessment"] == "shortfall"
    assert result[4]["missing_hours"] == 1
    assert all(d.blocks == [] for d in plan.days)
    # A task due on the horizon's last day + 1 is still planned.
    edge = make_plan(request([task(5, day(HORIZON_DAYS), 1)]))
    assert assessed(edge)[5]["assessment"] == "on_track"


def test_the_order_of_the_tasks_sent_does_not_change_the_plan():
    tasks = [task(i, day(i % 9), i % 4 + 1) for i in range(1, 12)]
    plan = make_plan(request(tasks))

    assert make_plan(request(list(reversed(tasks)))) == plan


def best_on_time_count(tasks: list[dict], free: list[int]) -> int:
    """By brute force: the most tasks that can all be done before their due day.

    A set fits if, taken by due day, each due day has enough free time before it.
    """
    before = [0]
    for units in free:
        before.append(before[-1] + units)
    jobs = [(t["deadline"], t["need"]) for t in tasks if t["deadline"] >= 0]
    for size in range(len(jobs), 0, -1):
        for chosen in combinations(jobs, size):
            needed = 0
            fits = True
            for deadline, need in sorted(chosen):
                needed += need
                if needed > before[deadline]:
                    fits = False
                    break
            if fits:
                return size
    return 0


def test_random_plans_keep_every_rule():
    rng = random.Random(2026)
    for _ in range(300):
        weekly = {name: rng.choice([0, 0.5, 1, 2, 3]) for name in WEEKDAYS}
        blocked = [day(rng.randrange(14)) for _ in range(rng.randrange(3))]
        raw = [
            {"deadline": rng.randrange(-1, 15), "need": rng.randrange(1, 13)}
            for _ in range(rng.randrange(1, 7))
        ]
        tasks = [
            task(i, day(r["deadline"]), r["need"] / 2)
            for i, r in enumerate(raw, start=1)
        ]
        plan = make_plan(request(tasks, weekly_hours=weekly, blocked_dates=blocked))
        result = assessed(plan)

        for d in plan.days:  # never more than the free hours of a day
            assert d.planned_hours == sum(b.hours for b in d.blocks) <= d.free_hours
        for i, r in enumerate(raw, start=1):
            if r["deadline"] < 0:
                assert result[i]["assessment"] == "overdue"
                continue
            # nothing on or after the due day, and nothing beyond the need
            assert not any(hours_by_day(plan, i)[r["deadline"] :])
            assert result[i]["planned_hours"] + result[i]["missing_hours"] == (
                r["need"] / 2
            )
        free = [
            0
            if (SUNDAY + timedelta(days=i)).isoformat() in blocked
            else int(weekly[WEEKDAYS[(SUNDAY + timedelta(days=i)).weekday()]] * 2)
            for i in range(15)
        ]
        on_time = sum(t["assessment"] == "on_track" for t in result.values())
        assert on_time == best_on_time_count(raw, free)
