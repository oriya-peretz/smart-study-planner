"""Create a demo account with sample courses and tasks, through the running API.

    uv run python scripts/demo_data.py            # backend at http://127.0.0.1:8000
    uv run python scripts/demo_data.py URL        # another address

The account is for local demos only. Running it again does nothing if the
account already exists.
"""

import sys
from datetime import datetime, timedelta

import httpx

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-planner-2026"


def main(base_url: str) -> None:
    api = httpx.Client(base_url=base_url, timeout=10)
    if api.post("/auth/signup", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).status_code == 409:
        print(f"{DEMO_EMAIL} already exists; nothing to do.")
        return
    token = api.post("/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).json()["access_token"]
    api.headers["Authorization"] = f"Bearer {token}"

    now = datetime.now().replace(second=0, microsecond=0)

    def at(days: int, hour: int, minute: int = 0) -> str:
        return (now + timedelta(days=days)).replace(hour=hour, minute=minute).isoformat()

    courses = {}
    for name in ["Automata", "Software Engineering", "Statistics", "Linear Algebra"]:
        courses[name] = api.post("/courses", json={"name": name}).raise_for_status().json()["id"]

    tasks = [
        {"title": "Exercise 3", "course_id": courses["Automata"], "type": "homework", "due_at": at(3, 23, 59),
         "estimated_hours": 4, "status": "in_progress", "link": "https://github.com/example/automata-ex3"},
        {"title": "Final exam", "course_id": courses["Automata"], "type": "exam", "due_at": at(40, 9),
         "estimated_hours": 20, "location": "Building 2, room 104"},
        {"title": "EX2 - Frontend", "course_id": courses["Software Engineering"], "type": "project",
         "due_at": at(26, 23, 59), "estimated_hours": 15, "link": r"C:\Users\me\smart-study-planner"},
        {"title": "Quiz 2", "course_id": courses["Statistics"], "type": "online_quiz", "due_at": at(1, 18),
         "estimated_hours": 1},
        {"title": "Lab report", "course_id": courses["Statistics"], "type": "submission", "due_at": at(-2, 23, 59),
         "notes": "Ask the TA about question 4"},
    ]
    for task in tasks:
        api.post("/tasks", json=task).raise_for_status()
    print(f"Created {DEMO_EMAIL} with {len(courses)} courses and {len(tasks)} tasks.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
