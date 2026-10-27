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

## Task model

| Field | Required | Notes |
|---|---|---|
| `title` | yes | 1-200 characters |
| `course` | yes | course name, 1-100 characters |
| `type` | yes | `exam`, `submission`, `online_quiz`, `homework`, `project` |
| `due_at` | yes | date and time, e.g. `2026-11-20T23:59`; stored as local time |
| `estimated_hours` | no | greater than 0 |
| `status` | no, **not for exams** | `todo` (default), `in_progress`, `done` |
| `link` | no, **not for exams** | URL or local path to the working files |
| `location` | no, **exams only** | where the exam takes place |
| `notes` | no | up to 2000 characters |

An exam's `status` is never sent: it is `todo` until the exam's date and time pass, then `done`.
Sending a field that does not fit the task's type returns `422`.

## API

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /health` | liveness check | 200 | |
| `POST /tasks` | create a task | 201 | 422 |
| `GET /tasks` | all tasks, most urgent first | 200 | |
| `GET /tasks/by-course` | tasks grouped by course, most urgent course first | 200 | |
| `GET /tasks/{id}` | one task | 200 | 404 |
| `PATCH /tasks/{id}` | change only the fields sent; `null` clears an optional field | 200 | 404, 422 |
| `DELETE /tasks/{id}` | delete a task | 204 | 404 |

**Urgency:** open tasks first, nearest `due_at` first (an overdue open task comes first); done tasks last.
Both list views accept `?include_done=false` to hide done tasks.

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

The image sets `TZ=Asia/Jerusalem`, so an exam becomes `done` at the right local time.
`docker volume rm planner-data` deletes the data permanently.

### Example requests

```bash
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" \
  -d '{"title": "Exercise 3", "course": "Automata", "type": "homework", "due_at": "2026-11-20T23:59", "estimated_hours": 4}'

curl http://localhost:8000/tasks
curl http://localhost:8000/tasks/by-course

curl -X PATCH http://localhost:8000/tasks/1 -H "Content-Type: application/json" -d '{"status": "in_progress"}'
curl -X DELETE http://localhost:8000/tasks/1
```

## Frontend

From `frontend/`, with the backend running:

```bash
uv run streamlit run streamlit_app.py
```

Open http://localhost:8501. Add a task from **Add a task** at the top; choose **By urgency** or **By course**; expand a task to see its details, edit it, mark it done or delete it.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | where the frontend sends API requests |

`127.0.0.1` rather than `localhost`: on Windows, `localhost` tries IPv6 first and adds about 2 seconds to every request.

## Project layout

```
backend/
  app/
    main.py        routes and startup
    models.py      task table and request/response models with validation
    db.py          database engine and per-request session
    ordering.py    the urgency and by-course views
  tests/           pytest tests
  Dockerfile
frontend/
  streamlit_app.py the page
  api.py           every HTTP call to the backend, with user-facing error messages
```

## AI-use note

Development was assisted by Claude (Claude Code). It drafted the project setup, models, routes, tests, Dockerfile, the Streamlit frontend and this README from my specifications.
I reviewed each change, ran the test suite (`uv run pytest`) and checked the API manually against a running server, including invalid input, missing records and persistence across restarts.
