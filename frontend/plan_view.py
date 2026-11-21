"""Weekly study plan: the free study time dialog, creating a plan, and the saved one.

Everything goes through the backend, which calls the AI service and saves the
plan. This page only reads the plan and asks for a new one when the user says so.
One primary action at a time: set free time first, then create or update the plan.
"""

import html
from datetime import date, datetime, timedelta

import streamlit as st

import account
import api
import dialogs
from labels import plain
from texts import date_time, day_label, duration, error_message, separator, t

# The Israeli week: the free time dialog lists the days from Sunday.
WEEK = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
HORIZON_DAYS = 56  # blocked dates can be chosen in the 8 weeks the plan looks at

# Each task's line says what the plan checked, never whether the work was done.
STATUS_COLORS = {"shortfall": "orange", "no_estimate": "gray", "later": "gray"}

# The week as clean day cards. auto-fill sets how many fit on a row; the grid
# follows the page's direction, so Sunday is on the right in Hebrew.
WEEK_STYLE = """
<style>
  .plan-week { display: grid; grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
               gap: .6rem; margin: .4rem 0 1.2rem; }
  .plan-day { border: 1px solid rgba(49, 51, 63, .15); border-radius: .7rem;
              padding: .6rem .75rem; }
  .plan-day.today { border-color: #B08D57; }
  .plan-day.off { background: #F7F5F0; border-color: transparent; }
  .plan-head { font-weight: 500; font-size: .8rem; }
  .plan-free { font-size: .68rem; color: #7A7266; margin-bottom: .3rem; }
  .plan-block { border-inline-start: 2px solid #B08D57; padding-inline-start: .5rem;
                margin: .4rem 0; }
  .plan-title { font-size: .78rem; line-height: 1.3; }
  .plan-meta { font-size: .68rem; color: #7A7266; }
</style>
"""


def bold(text: str) -> str:
    """Bold text, then a space. Markdown ends bold only before a space or the line's
    end when the text ends in punctuation (a Hebrew date ends in ׳), and the
    Hebrew separator starts with an invisible direction mark."""
    return f"**{text}** "


def study_hours(limits: api.Constraints) -> None:
    """The dialog body: free hours per weekday, blocked dates, and the note."""
    st.caption(t("hours_intro"))
    today = date.today()
    choices = [today + timedelta(days=i) for i in range(HORIZON_DAYS)]
    saved = [date.fromisoformat(day) for day in limits["blocked_dates"]]
    # Dates saved earlier stay choosable, even when they are already past.
    choices = sorted(set(choices) | set(saved))
    with st.form("study-hours", border=False):
        weekly = {}
        for row in (WEEK[:4], WEEK[4:]):
            for column, day in zip(st.columns(4), row):
                weekly[day] = column.number_input(
                    t(f"day_{day}"),
                    min_value=0.0,
                    max_value=16.0,
                    value=float(limits["weekly_hours"][day]),
                    step=0.5,
                    format="%.1f",
                    key=f"hours-{day}",
                )
        blocked = st.multiselect(
            t("blocked_dates"),
            choices,
            default=saved,
            format_func=day_label,
            placeholder=t("choose_dates"),
            help=t("blocked_help"),
            key="hours-blocked",
        )
        note = st.text_area(
            t("plan_note"),
            limits["note"],
            max_chars=500,
            help=t("plan_note_help"),
            key="hours-note",
        )
        if st.form_submit_button(
            t("save"), type="primary", key="hours-submit", width="stretch"
        ):
            body = {
                "weekly_hours": weekly,
                "blocked_dates": [day.isoformat() for day in sorted(blocked)],
                "note": note,
            }
            try:
                account.backend().save_constraints(body)
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                dialogs.notify(t("hours_saved"))


def build_button(plan: api.Plan | None) -> bool:
    """Create or Update: the page's primary action once free time is set."""
    return st.button(
        t("rebuild_plan") if plan else t("build_plan"),
        key="build-plan",
        type="primary",
        icon=":material/auto_awesome:",
    )


def build() -> None:
    """Ask for a new plan. A failure says what it means and keeps the saved plan."""
    try:
        with st.spinner(t("plan_building")):
            account.backend().build_plan()
    except api.NotLoggedIn:
        account.end_session("session_ended")
    except api.BackendError as exc:
        technical = {
            "ai_unavailable": "tech_unavailable",
            "ai_bad_output": "tech_bad_output",
        }
        if exc.code in technical:
            failed = (
                "plan_failed" if exc.code == "ai_unavailable" else "plan_failed_bad"
            )
            st.error(t(failed))
            with st.expander(t("tech_details")):
                st.caption(t(technical[exc.code]))
        else:
            st.error(error_message(exc))
    else:
        dialogs.notify(t("plan_built"))


def source_line(plan: api.Plan) -> str:
    if plan["source"] == "model":
        return t("plan_by_model")
    if plan["fallback_reason"]:
        return t("plan_fallback", reason=t(f"reason_{plan['fallback_reason']}"))
    return t("plan_by_rules")


def week(plan: api.Plan) -> None:
    """Seven day cards: what to study, for which course, and for how long."""
    today = date.today()
    cards = []
    for day in plan["days"]:
        when = date.fromisoformat(day["date"])
        head = f'<div class="plan-head">{html.escape(day_label(when))}</div>'
        if not day["free_hours"]:
            cards.append(
                f'<div class="plan-day off">{head}'
                f'<div class="plan-free">{html.escape(t("day_off"))}</div></div>'
            )
            continue
        free = t("day_free", h=duration(day["free_hours"]))
        if when == today:
            free = t("due_today").capitalize() + " · " + free
        blocks = "".join(
            '<div class="plan-block">'
            f'<div class="plan-title">{html.escape(block["title"])}</div>'
            f'<div class="plan-meta">{html.escape(block["course"])} · '
            f"{html.escape(duration(block['hours']))}</div></div>"
            for block in day["blocks"]
        )
        today_class = " today" if when == today else ""
        cards.append(
            f'<div class="plan-day{today_class}">{head}'
            f'<div class="plan-free">{html.escape(free)}</div>{blocks}</div>'
        )
    st.html(WEEK_STYLE + f'<div class="plan-week">{"".join(cards)}</div>')


def status(item: dict, due_word: str) -> str:
    """One line on what the plan checked for this task."""
    match item["assessment"]:
        case "on_track":
            return t("status_planned")
        case "shortfall":
            missing = item["missing_hours"]
            key = "status_short_one" if missing <= 1 else "status_short_many"
            return t(key, h=duration(missing), due=due_word)
        case "no_estimate":
            kind = "exam" if item["type"] == "exam" else "task"
            return t(f"status_no_estimate_{kind}")
        case other:
            return t(f"status_{other}")


def breakdown(item: dict, due_word: str) -> None:
    """The full numbers, shown only when the user opens the task."""
    if item["needed_hours"] is None:
        st.caption(t("detail_edit_hint"))
        return
    lines = [t("detail_needed", h=duration(item["needed_hours"]))]
    planned = t("detail_planned", due=due_word, h=duration(item["planned_hours"]))
    this_week = item["planned_hours_this_week"]
    if this_week and this_week != item["planned_hours"]:
        planned += f" ({t('detail_this_week', h=duration(this_week))})"
    lines.append(planned)
    if item["missing_hours"]:
        lines.append(t("detail_missing", h=duration(item["missing_hours"])))
    st.caption(separator().join(lines))
    if item["missing_hours"]:
        st.caption(t("detail_short_hint"))


def standing(plan: api.Plan) -> None:
    st.markdown(f"##### {t('plan_tasks')}")
    for item in plan["tasks"]:
        due_word = t("due_word_exam" if item["type"] == "exam" else "due_word_task")
        line = status(item, due_word)
        if color := STATUS_COLORS.get(item["assessment"]):
            line = f":{color}[{line}]"
        due = day_label(datetime.fromisoformat(item["due_at"]).date())
        label = separator().join(
            [bold(plain(item["title"])), plain(item["course"]), due, line]
        )
        with st.expander(label):
            breakdown(item, due_word)


def details(plan: api.Plan) -> None:
    made = date_time(datetime.fromisoformat(plan["created_at"]))
    with st.expander(t("plan_made", when=made) + separator() + t("plan_details")):
        st.caption(t("plan_basis"))
        st.caption(source_line(plan))


def plan_page() -> None:
    """The whole Weekly study plan page."""
    backend = account.backend()
    try:
        limits = backend.get_constraints()
        plan = backend.get_plan()
    except api.NotLoggedIn:
        account.end_session("session_ended")
    except api.BackendError as exc:
        st.error(error_message(exc))
        st.stop()

    outdated = plan is not None and plan["outdated"]
    clicked = False
    st.caption(t("plan_subtitle"))
    with st.container(
        key="plan-bar",
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
    ):
        # Before any free time is saved, setting it is the main action.
        if st.button(
            t("edit_hours"),
            key="edit-hours",
            type="tertiary" if limits["saved"] else "primary",
            icon=":material/schedule:",
        ):
            dialogs.open_dialog("study-hours")
        if limits["saved"] and not outdated:
            clicked = build_button(plan)
    if outdated:
        # The update button lives here only, so there is never a second one.
        with st.container(
            key="plan-outdated", horizontal=True, vertical_alignment="center"
        ):
            st.markdown(t("plan_outdated"), width="stretch")
            clicked = build_button(plan)

    if clicked:
        build()
    if not limits["saved"]:
        st.info(t("plan_set_hours_first"))
    elif plan is None:
        st.caption(t("plan_none_yet"))
    if plan is not None:
        week(plan)
        standing(plan)
        details(plan)

    if st.session_state.get("dialog", {}).get("name") == "study-hours":
        dialogs.open_as("dlg_study_hours", study_hours, limits, width="medium")
