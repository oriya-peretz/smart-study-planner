# Smart Study Planner

One place for a student to collect every exam, assignment and project across all courses:
what is due, when, how long it will take, and where the work lives.
Tasks can be viewed in one list by urgency, or grouped by course.
A later version adds an AI assistant that suggests a study plan from the student's workload and deadlines.

The repository holds two services:

- `backend/`: a FastAPI service with SQLite storage (the API below)
- `frontend/`: a Streamlit page in the browser that talks to the backend over HTTP

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

Each student has her own account and sees only her own courses and tasks.

- `POST /auth/signup` with `{"email", "password"}` (password: 8-128 characters) creates an account.
- `POST /auth/login` with the same body returns `{"access_token": "..."}`.
- Every `/courses` and `/tasks` request sends it as `Authorization: Bearer <token>`; without a valid token the answer is `401`.
- Another user's course or task answers `404`, as if it did not exist.
- Passwords are stored only as salted scrypt hashes; tokens are stored only as SHA-256 hashes and expire after 14 days.
- `POST /auth/logout` ends the session; `GET /auth/me` returns the logged-in user.

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
| `GET /auth/me` | the logged-in user | 200 | 401 |
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

Open http://localhost:8501, then **Sign up** or **Log in** (the login lasts until you log out or reload the page). **By urgency** shows one numbered list, the most urgent first. **By course** shows a card per course; **+ New course** adds one, and **Open** shows that course's tasks. **Add task** opens a form whose fields follow the task type. Expand a task to see its details, mark it done, or edit and delete it.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | where the frontend sends API requests |

`127.0.0.1` rather than `localhost`: on Windows, `localhost` tries IPv6 first and adds about 2 seconds to every request.

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
  views.py         the screens: numbered list, course grid, course page
  dialogs.py       pop-up forms: add/edit task, add/rename/delete course
  labels.py        names, icons and due-date wording
  api.py           every HTTP call to the backend, with user-facing error messages
  .streamlit/config.toml  theme: white and gold, Jost font, round buttons
```

## AI-use note

Development was assisted by Claude (Claude Code). It drafted the project setup, models, routes, tests, Dockerfile, the Streamlit frontend and this README from my specifications.
I reviewed each change, ran the test suite (`uv run pytest`) and checked the API manually against a running server, including invalid input, missing records and persistence across restarts.
