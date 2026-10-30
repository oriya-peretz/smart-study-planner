# Smart Study Planner

One place for a student to collect every exam, assignment and project across all courses:
what is due, when, how long it will take, and where the work lives.
Tasks can be viewed in one list by urgency, or grouped by course.
A later version adds an AI assistant that suggests a study plan from the student's workload and deadlines.

The repository holds three services:

- `backend/`: a FastAPI service with SQLite storage (the API below)
- `frontend/`: a Streamlit page in the browser that talks to the backend over HTTP
- `ai-service/`: a FastAPI service that builds a study plan; it stores nothing (in progress, see [AI service](#ai-service))

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Run each service in its own terminal:

```bash
cd backend
uv run fastapi dev app/main.py
```

```bash
cd frontend
uv run streamlit run streamlit_app.py
```

Open http://localhost:8501 for the app, or http://localhost:8000/docs for the API documentation.

## Accounts

Every student has an account and sees only their own courses and tasks.

- `POST /auth/signup` with `{"email", "password"}` (password: 8-128 characters) creates an account.
- `POST /auth/login` with the same body returns `{"access_token": "..."}`.
- Every `/courses` and `/tasks` request sends it as `Authorization: Bearer <token>`; without a valid token the answer is `401`.
- Another user's course or task answers `404`, as if it did not exist.
- Passwords are stored only as salted scrypt hashes; tokens are stored only as SHA-256 hashes and expire after 14 days.
- `POST /auth/logout` ends the session; `GET /auth/me` returns the logged-in user, and `PATCH /auth/me` with `{"language": "en" | "he"}` changes their interface language (default `en`).

In `/docs`, log in with `POST /auth/login`, copy the token, and paste it under **Authorize**.

### Demo account

With the backend running, from `backend/`:

```bash
uv run python scripts/demo_data.py
```

creates `demo@example.com` (password in `scripts/demo_data.py`) with sample courses and tasks. Running it again changes nothing.

## Courses

A course has an `id` and a `name` (1-100 characters, unique ignoring upper/lower case).
Every task belongs to one course.

## Task model

| Field | Required | Notes |
|---|---|---|
| `title` | yes | 1-200 characters |
| `course_id` | yes | an existing course (see Courses); responses also include `course: {id, name}` |
| `type` | yes | `exam`, `submission`, `online_quiz`, `homework`, `project` |
| `due_at` | yes | date and time, e.g. `2026-11-20T23:59`; stored as local time |
| `estimated_hours` | no | greater than 0 |
| `status` | no, **not for exams** | `todo` (default), `in_progress`, `done` |
| `link` | no, **not for exams** | URL or local path to the working files |
| `location` | no, **exams only** | where the exam takes place |
| `notes` | no | up to 2000 characters |

An exam's `status` is never sent: it is `todo` until the exam's date and time pass, then `past` (past, not done: the date passing does not mean the exam was taken).
Sending a field that does not fit the task's type returns `422`.

## API

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /health` | liveness check (no token needed) | 200 | |
| `POST /auth/signup` | create an account | 201 | 409 email taken, 422 |
| `POST /auth/login` | get a token | 200 | 401 wrong email or password |
| `POST /auth/logout` | end this session | 204 | 401 |
| `GET /auth/me` | the logged-in user, with their language | 200 | 401 |
| `PATCH /auth/me` | change the interface language (`en` or `he`) | 200 | 401, 422 |
| `GET /courses` | all courses by name | 200 | |
| `POST /courses` | create a course | 201 | 409 name taken, 422 |
| `PATCH /courses/{id}` | rename a course | 200 | 404, 409, 422 |
| `DELETE /courses/{id}` | delete a course without tasks | 204 | 404, 409 has tasks |
| `POST /tasks` | create a task | 201 | 422 (also for an unknown `course_id`) |
| `GET /tasks` | all tasks, most urgent first | 200 | |
| `GET /tasks/by-course` | every course with its tasks; most urgent course first, courses without tasks last | 200 | |
| `GET /tasks/{id}` | one task | 200 | 404 |
| `PATCH /tasks/{id}` | change only the fields sent; `null` clears an optional field | 200 | 404, 422 |
| `DELETE /tasks/{id}` | delete a task | 204 | 404 |

All course and task routes need a token and answer `401` without one.

**Urgency:** open tasks first, nearest `due_at` first (an overdue open task comes first); done tasks and past exams last.
Both list views accept `?include_done=false` to hide done tasks and past exams.

Interactive documentation is served at `/docs` while the server runs.

## Backend

### Run locally

From `backend/`. uv installs the Python version from `.python-version` (3.14) and the locked dependencies.

```bash
uv run fastapi dev app/main.py
```

Open http://localhost:8000/docs. Data is stored in `backend/data/app.db`, which is created on first start.

### Database changes

`create_all` creates missing tables but never changes existing ones. Columns added to a model later are listed in `ADDED_COLUMNS` in `app/db.py` and added at startup with their default, so an existing `data/app.db` keeps its data.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | where the SQLite database lives |

See `.env.example`.

### Run the tests

From `backend/`:

```bash
uv run pytest
```

Tests use an in-memory database, so they never touch `data/app.db`.
`tests/test_restart.py` checks that tasks survive a server restart, using a temporary database file.

### Run with Docker

From `backend/`:

```bash
docker build -t smart-study-planner .
docker run -d --name planner -p 127.0.0.1:8000:8000 -v planner-data:/app/data smart-study-planner
```

Open http://localhost:8000/docs. Stop `uv run fastapi dev` first, or port 8000 will already be taken.

The database lives in the named volume `planner-data`, so tasks survive replacing the container:

```bash
docker rm -f planner
docker run -d --name planner -p 127.0.0.1:8000:8000 -v planner-data:/app/data smart-study-planner
```

The image sets `TZ=Asia/Jerusalem`, so an exam becomes `past` at the right local time.
`docker volume rm planner-data` deletes the data permanently.

### Example requests

```bash
curl -X POST http://localhost:8000/auth/signup -H "Content-Type: application/json" -d '{"email": "me@example.com", "password": "a long password"}'
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email": "me@example.com", "password": "a long password"}'
TOKEN=...   # the access_token from the answer above

curl -X POST http://localhost:8000/courses -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name": "Automata"}'

curl -X POST http://localhost:8000/tasks -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "Exercise 3", "course_id": 1, "type": "homework", "due_at": "2026-11-20T23:59", "estimated_hours": 4}'

curl http://localhost:8000/tasks -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/tasks/by-course -H "Authorization: Bearer $TOKEN"

curl -X PATCH http://localhost:8000/tasks/1 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"status": "in_progress"}'
curl -X DELETE http://localhost:8000/tasks/1 -H "Authorization: Bearer $TOKEN"
```

## Frontend

From `frontend/`, with the backend running:

```bash
uv run streamlit run streamlit_app.py
```

Open http://localhost:8501, then **Sign up** or **Log in** (the login lasts until you log out or reload the page). **By urgency** shows one numbered list, the most urgent first. **By course** shows a card per course with all of its tasks; **+ New course** adds a course, and each card has its own **Add task** and **Settings** (rename or delete). **Add task** opens a form whose fields follow the task type. Expand a task to see its details, mark it done, or edit and delete it.

**Language:** the **English | עברית** switch at the top changes every interface text; Hebrew is laid out right to left. While logged in the choice is saved to the account, and logging in brings it back. What users type (course names, titles, notes) is never translated.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | where the frontend sends API requests |

### Frontend tests

From `frontend/`:

```bash
uv run pytest
uv run ruff check .
```

`tests/test_app.py` runs the page with Streamlit's `AppTest` (no browser) and fakes the backend with `respx`, so each state can be produced on demand: the landing screen, log in and sign up (including a wrong password and a validation error), both views and the empty state, the backend being down, an expired session, a write whose reply was lost, and the exact JSON the forms send with the user's token.
`tests/test_boundary.py` checks that only `api.py` talks HTTP.

What these tests do not cover: a real browser, and whether the real backend still answers in the shapes the fakes use. The backend's tests cover the backend's side of that contract.

`127.0.0.1` rather than `localhost`: on Windows, `localhost` tries IPv6 first and adds about 2 seconds to every request.

## AI service

`ai-service/` turns a user's unfinished tasks and free hours into a study plan. It is a separate process on port 8001 and stores nothing: the caller sends everything the plan needs, and the backend will own the saved plan.
This first version is deterministic (no model yet). A Pydantic AI agent will propose plans next, checked against the same rules, with this plan as the fallback.

From `ai-service/`:

```bash
uv run fastapi dev --port 8001
uv run pytest
uv run ruff check .
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{"status": "ok"}` |
| POST | `/plan` | a 7-day plan and an assessment of each task |

The request has a `start_date`, the user's `constraints` (`weekly_hours` from `sunday` to `saturday`, 0 to 16 in half hours, and `blocked_dates` with no study time) and the `tasks` (`id`, `title`, `course`, `type`, `due_at` in local time, optional `estimated_hours`). Unknown fields, duplicate task ids and times with a time zone are rejected with `422`.

```bash
curl -s localhost:8001/plan -H "content-type: application/json" -d '{
  "start_date": "2026-11-01",
  "constraints": {"weekly_hours": {"sunday": 2, "monday": 2, "tuesday": 2}},
  "tasks": [{"id": 1, "title": "Sheet 3", "course": "Algorithms", "type": "homework",
             "due_at": "2026-11-04T23:59", "estimated_hours": 3}]
}'
```

The response lists 7 `days` (free hours, planned hours, and hours per task) and the `tasks` in priority order, each with its `assessment`: `on_track`, `shortfall` (with `missing_hours`), `no_estimate`, `overdue`, or `later` (due after the 8 weeks the plan looks at).

`all_fit` is true only when every task sent is `on_track`. A task the plan could not check (`no_estimate`, `overdue`, `later`) makes it false, even with no shortfall, because the plan cannot claim that task fits; `tasks` gives the reason.

Each entry in a day's `blocks` is **hours allocated to one task on that day, not a study session**: it has no start time, and no minimum length or break rules are checked, so a block can be as short as half an hour.

**Rules the code enforces:**

- A day's free hours come only from the constraints, and no day is planned beyond them.
- A task is worked on only on days before its due date. Only the date counts: the due day is never planned, even for a task due at 23:59, so the plan aims to finish a day early and can report a shortfall for a task that could still be finished on the day itself.
- Estimates are rounded up to half hours. They are estimates: the plan reports how much fits, not that the work will take exactly that long.
- **Slack** is the free time before a task's due date minus the hours it needs. The next half hour always goes to the task with the least slack, so a long task due on Friday can come before a short one due on Thursday.
- When not everything fits, the plan keeps the largest possible number of tasks on time (the Moore-Hodgson rule), gives the rest whatever time is left, and reports each one's missing hours. Nothing is hidden or silently dropped.

`tests/test_planner.py` checks each rule, plus 300 random cases against a brute-force answer: no day is overbooked, nothing is planned on or after a due date, and the number of tasks on time is the best possible.

## Project layout

```
backend/
  app/
    main.py        routes and startup
    auth.py        accounts: password hashing, tokens, who is calling
    models.py      task table and request/response models with validation
    db.py          database engine and per-request session
    ordering.py    the urgency and by-course views
  tests/           pytest tests
  scripts/demo_data.py  creates a demo account with sample data
  Dockerfile
frontend/
  streamlit_app.py the page Streamlit runs: loads data, picks a screen
  account.py       landing screen, log in, sign up, log out
  views.py         the screens: numbered list, and course cards with their tasks
  dialogs.py       pop-up forms: add/edit task, add/rename/delete course
  labels.py        names, icons and due-date wording
  texts.py         every interface text in English and Hebrew, and the current language
  api.py           every HTTP call to the backend, with user-facing error messages
  .streamlit/config.toml  theme: white and gold, Jost font, round buttons, 20 px base size
ai-service/
  app/
    main.py        /health and POST /plan
    schemas.py     the request and response contract, with validation
    planner.py     the deterministic plan: free hours, slack, shortfalls
  tests/           pytest tests, including randomized checks of the rules
```

## AI-use note

Development was assisted by Claude (Claude Code). It drafted the project setup, models, routes, tests, Dockerfile, the Streamlit frontend and this README from my specifications.
I reviewed each change, ran the test suite (`uv run pytest`) and checked the API manually against a running server, including invalid input, missing records and persistence across restarts.
