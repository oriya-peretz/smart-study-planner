"""My plan: the study hours dialog, building a plan, and showing the saved one.

Everything goes through the backend, which calls the AI service and saves the
plan. This page only reads the plan and asks for a new one when the user says so.
"""

from datetime import date, datetime, timedelta

import streamlit as st

import account
import api
import dialogs
from labels import plain
from texts import date_time, day_label, error_message, separator, t

# The Israeli week: the hours dialog lists the days from Sunday.
WEEK = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
HORIZON_DAYS = 56  # blocked dates can be chosen in the 8 weeks the plan looks at

ASSESSMENT_COLORS = {
    "on_track": "green",
    "shortfall": "orange",
    "no_estimate": "gray",
    "overdue": "red",
    "later": "gray",
}


def hours(value: float) -> str:
    return f"{value:g}"


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


def build(label: str, saved_hours: bool) -> None:
    """The Build / Rebuild button. A failure keeps the saved plan on screen."""
    if not st.button(
        label,
        key="build-plan",
        type="primary",
        icon=":material/auto_awesome:",
        disabled=not saved_hours,
        width="stretch",
    ):
        return
    try:
        with st.spinner(t("plan_building")):
            account.backend().build_plan()
    except api.NotLoggedIn:
        account.end_session("session_ended")
    except api.BackendError as exc:
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
    st.markdown(f"#### {t('plan_week')}")
    for day in plan["days"]:
        heading = bold(day_label(date.fromisoformat(day["date"])))
        if day["free_hours"]:
            amount = t(
                "day_hours",
                planned=hours(day["planned_hours"]),
                free=hours(day["free_hours"]),
            )
        else:
            amount = t("day_off")
        lines = [heading + separator() + f":gray[{amount}]"]
        # Plain lines under the day, not a Markdown list: a list's bullet and
        # text drift apart when an English title sits in a right-to-left page.
        for block in day["blocks"]:
            lines.append(
                separator().join(
                    [
                        plain(block["title"]),
                        plain(block["course"]),
                        t("hours", h=hours(block["hours"])),
                    ]
                )
            )
        st.markdown("  \n".join(lines))  # two spaces + newline: a line break


def assessment(item: dict) -> str:
    match item["assessment"]:
        case "on_track":
            return t(
                "assess_on_track",
                planned=hours(item["planned_hours"]),
                needed=hours(item["needed_hours"]),
            )
        case "shortfall":
            return t("assess_shortfall", missing=hours(item["missing_hours"]))
        case other:
            return t(f"assess_{other}")


def standing(plan: api.Plan) -> None:
    st.markdown(f"#### {t('plan_tasks')}")
    for item in plan["tasks"]:
        color = ASSESSMENT_COLORS[item["assessment"]]
        parts = [
            bold(plain(item["title"])),
            plain(item["course"]),
            f":{color}[{assessment(item)}]",
        ]
        st.markdown(separator().join(parts))


def show(plan: api.Plan) -> None:
    made = datetime.fromisoformat(plan["created_at"])
    st.caption(t("plan_made", when=date_time(made)) + separator() + source_line(plan))
    if plan["outdated"]:
        st.warning(t("plan_outdated"), icon=":material/update:")
    elif plan["all_fit"]:
        st.success(t("plan_all_fit"))
    week(plan)
    standing(plan)
    st.caption(t("plan_estimates"))


def plan_page() -> None:
    """The whole My plan page."""
    backend = account.backend()
    try:
        limits = backend.get_constraints()
        plan = backend.get_plan()
    except api.NotLoggedIn:
        account.end_session("session_ended")
    except api.BackendError as exc:
        st.error(error_message(exc))
        st.stop()

    hours_col, build_col = st.columns(2)
    if hours_col.button(
        t("edit_hours"),
        key="edit-hours",
        icon=":material/schedule:",
        width="stretch",
    ):
        dialogs.open_dialog("study-hours")
    with build_col:
        build(t("rebuild_plan") if plan else t("build_plan"), limits["saved"])

    if not limits["saved"]:
        st.info(t("plan_set_hours_first"))
    elif plan is None:
        st.info(t("plan_none_yet"))
    if plan is not None:
        show(plan)

    if st.session_state.get("dialog", {}).get("name") == "study-hours":
        dialogs.open_as("dlg_study_hours", study_hours, limits, width="medium")
