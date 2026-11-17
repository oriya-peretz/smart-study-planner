"""The product's operational principle, in a real browser against the real stack.

After a user adds a task to a course, it appears in their list; after they log out
and back in, it is still there (the backend stored it); after they delete it, it is
gone. Needs the backend and the frontend running, then, from frontend/:

    uv run pytest e2e --base-url http://127.0.0.1:8501 --browser-channel chrome

Each run signs up a new throwaway account, so it never touches anyone's data.
"""

import uuid

from playwright.sync_api import Locator, Page, expect

RUN = uuid.uuid4().hex[:8]
EMAIL = f"e2e-{RUN}@example.com"
PASSWORD = f"e2e-password-{RUN}"


def widget(page: Page, key: str) -> Locator:
    """A Streamlit widget by its key: Streamlit gives its element a st-key-<key> class."""
    return page.locator(f".st-key-{key}")


def log_in(page: Page, signing_up: bool = False) -> None:
    start = "go-signup" if signing_up else "go-login"
    widget(page, start).get_by_role("button").click()
    page.get_by_role("textbox", name="Email").fill(EMAIL)
    page.get_by_role("textbox", name="Password").fill(PASSWORD)
    widget(page, "auth-submit").get_by_role("button").click()
    expect(widget(page, "log-out")).to_be_visible()


def test_a_task_outlives_the_session_and_can_be_deleted(page: Page):
    course = f"E2E course {RUN}"
    title = f"E2E task {RUN}"

    page.goto("/")
    log_in(page, signing_up=True)
    expect(page.get_by_text("Start by adding a course")).to_be_visible()

    # A course, from the + card in the by-course view.
    widget(page, "view").get_by_text("By course").click()
    widget(page, "new-course").get_by_role("button").click()
    page.get_by_role("textbox", name="Course name").fill(course)
    page.get_by_role("button", name="Add course").click()
    expect(page.get_by_text(f"Added the course {course}.")).to_be_visible()

    # A task, from that course's card; the course is already chosen.
    page.locator("[class*='st-key-course-add-']").get_by_role("button").click()
    page.get_by_role("dialog").get_by_role("textbox", name="Title").fill(title)
    widget(page, "add-submit").get_by_role("button").click()
    expect(page.get_by_text(f"Added {title}.")).to_be_visible()

    # A new session sees it, so it came from the backend, not from this page.
    widget(page, "log-out").get_by_role("button").click()
    expect(page.get_by_text("You have logged out.")).to_be_visible()
    log_in(page)
    task = page.get_by_text(title, exact=True)
    expect(task).to_be_visible()

    task.click()  # opens the task's details
    page.get_by_role("button", name="Edit").click()
    page.get_by_role("button", name="Delete task").click()
    page.get_by_role("button", name="Yes, delete").click()
    expect(page.get_by_text(f"Deleted {title}.")).to_be_visible()
    expect(page.get_by_text(title, exact=True)).to_have_count(0)
