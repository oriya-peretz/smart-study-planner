# Smart Study Planner

One place for a student to collect every exam, assignment and project across all courses:
what is due, when, how long it will take, and where the work lives.
Tasks can be viewed in one list by urgency, or grouped by course.
A later version adds an AI assistant that suggests a study plan from the student's workload and deadlines.

The repository holds three services:

- `backend/`: a FastAPI service with SQLite storage (the API below)
- `frontend/`: a Streamlit page in the browser that talks to the backend over HTTP
- `ai-service/`: a FastAPI service with a Pydantic AI agent that builds a study plan; it stores nothing, and only the backend calls it (in progress, see [AI service](#ai-service))

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
| `GET /constraints` | the user's free hours per weekday, blocked dates and note; `saved: false` before the first save | 200 | |
| `PUT /constraints` | replace them | 200 | 422 |
| `POST /plan` | build a new study plan now, through the AI service, and save it | 200 | 409 no constraints yet, 502, 503 |
| `GET /plan` | the saved plan, with `outdated` | 200 | 404 no plan yet |

All course, task, constraint and plan routes need a token and answer `401` without one.

**Urgency:** open tasks first, nearest `due_at` first (an overdue open task comes first); done tasks and past exams last.
Both list views accept `?include_done=false` to hide done tasks and past exams.

Interactive documentation is served at `/docs` while the server runs.

### The study plan

```text
browser -> frontend -> backend  --POST /plan-->  ai-service
                         |  (checks the answer, then saves it)
                         v
                       SQLite (only the backend reads and writes it)
```

**Constraints** are the user's hard limits: free hours for each day of the week (0 to 16, in half hours), dates with no study time, and an optional note (up to 500 characters, such as "keep Thursday light") that guides the model but cannot change the limits.

**`POST /plan`** reads the user's unfinished tasks (done tasks and past exams are left out) and constraints, sends them to the AI service with today as the first day, and saves the answer as the user's one current plan. It runs only when the user asks. **`GET /plan`** never calls the AI service; its `outdated` is `true` once a task, the constraints or the note changed since the plan was made, or once the plan's first day has passed. Each block and task in the answer carries the title and course it had when the plan was made.

**The backend checks the AI answer itself before saving it**, because only the backend writes data. The answer must match the backend's own copy of the contract (`app/ai_contract.py`), and then:

- start on the day that was sent and list exactly the seven days from it;
- give each day the user's own free hours (none on a blocked date), and plan no more than that;
- have blocks that add up to the planned hours, each with hours, each for a task that was sent, and each before that task's due day;
- assess every task that was sent exactly once.

**Errors:**

| What happened | `POST /plan` answers | Retried? | The saved plan |
|---|---|---|---|
| No constraints saved yet | `409 {"detail": "Set your free study hours first."}`, with no AI call | | unchanged |
| AI service refused the connection, timed out, or answered `503`/`504` | `503 {"detail": "AI service unavailable"}` | yes: 3 attempts in all, 0.5 s and 1 s apart | unchanged |
| AI service answered `500` | `503 {"detail": "AI service unavailable"}` | no | unchanged |
| AI service answered `4xx`, a broken body, or a plan that fails a check above | `502 {"detail": "AI service returned invalid output"}` | no: the same request gets the same answer | unchanged |
| The model failed inside the AI service | `200` with the baseline plan, `source: "baseline"` and a `fallback_reason` | inside the AI service | replaced |

Retries happen in one layer only, the backend's AI client. Repeating `POST /plan` to the AI service is safe, since it stores nothing and the backend saves only the answer it accepts; each attempt may still cost model work. The call has a timeout per phase (connect 2 s, read 30 s, write 5 s, pool 2 s), and the AI service stops its model after 25 s, so it answers within the read timeout. No database write is open while the backend waits.

Observed on Windows, with the AI service stopped: `POST /plan` answered `503` after about 8 seconds. On Windows a connection to a closed local port waits for the 2-second connect timeout instead of failing at once, so three attempts and the 1.5 seconds between them add up. Ordinary task and course routes kept working.

**The contract:** `tests/test_contract.py` compares the backend's copy of the contract with `tests/ai_openapi.json`, a snapshot of the schema the AI service publishes. Everything the backend sends must be accepted exactly, and everything it reads must exist with the same type and limits. After changing the AI service's contract, regenerate the snapshot from the repository root, then run the backend tests:

```bash
cd ai-service
uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=1, sort_keys=True))" > ../backend/tests/ai_openapi.json
```

`tests/test_plan.py` fakes the AI service with `httpx.MockTransport`, so the backend tests need no network and no AI service.

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
| `AI_SERVICE_URL` | `http://127.0.0.1:8001` | where the backend sends `POST /plan` |

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

Open http://localhost:8501, then **Sign up** or **Log in** (the login lasts until you log out or reload the page). The switch at the top chooses between two screens, **Tasks and exams** (shown first) and **Weekly study plan**. Each screen has one main action; quieter actions and details open on demand.

**Tasks and exams:** **By due date** shows one numbered list, the nearest due date first (open items before finished ones). **By course** shows a card per course with all of its tasks; the **+** card adds a course, and each card has its own **Add** and **Edit course** (rename or delete). **Add a task or exam** opens a form whose fields follow the type. Open a task to see its details, mark it done, or **Edit** it: the edit form also changes its status and deletes it.

**Weekly study plan:**

- **Free study time** opens a dialog for the hours free on each day of the week (in half hours), the dates with no study time (chosen from the next 8 weeks), and an optional note for the plan. Before it is saved, it is the screen's main action.
- **Create study plan**, or **Update study plan** once there is one, asks the backend for a plan from the open tasks; it can take up to a minute, so the page shows a spinner.
- The week is a grid of day cards, Sunday to Saturday (right to left in Hebrew), as many per row as the screen fits. Each card shows the day's free time and what to study, for which course, for how long, in words such as "1.5 hours" or "שעה וחצי".
- Each task has one line on what the plan checked, in planning words: all of its study time is in the plan, the plan is still some hours short before the due date, it needs an estimate, its date has passed, or it is due after 8 weeks. Opening it shows the study time needed, in the plan (and this week), and still missing.
- When tasks or free time change, or the plan's first day passes, a short note says the plan is out of date, with the one **Update study plan** button next to it. The plan is never rebuilt without that click.
- **Details**, at the bottom, says the hours are planned study time based on the user's estimates, not work done, and whether the AI model arranged the week or the planning rules calculated it, and why.
- If the AI service is down or its answer cannot be used, a short sentence says the previous plan is kept; the technical cause is under **Technical details**.

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
`tests/test_plan_page.py` covers the weekly study plan the same way: the one main action in each state (no free time yet, no plan yet, a plan, an outdated plan with a single update button), the day cards (with titles escaped as HTML), each task's planning line and its breakdown, the details, the exact free time JSON sent, a 422 in words, the AI service down (503) or answering badly (502) with the saved plan still shown and technical details on demand, the backend down, the 100-second timeout, Hebrew, and Hebrew durations.
`tests/test_boundary.py` checks that only `api.py` talks HTTP.

#### End-to-end test in a real browser

`e2e/test_e2e.py` replays the product's main promise with Playwright, against the real frontend, backend and database: after a user adds a task to a course, it appears; after they log out and back in, it is still there, so it came from the backend; after they delete it, it is gone. Each run signs up a new throwaway account (`e2e-<random>@example.com`).

Start the backend and the frontend as above, then from `frontend/`:

```bash
uv run pytest e2e --base-url http://127.0.0.1:8501 --browser-channel chrome
```

`--browser-channel chrome` uses an installed Google Chrome. Without Chrome, download Playwright's own browser once with `uv run playwright install chromium` and drop the flag. Plain `uv run pytest` does not run this test, because it needs the running stack; CI does not run it yet.

What these tests do not cover: every screen in a real browser (the e2e test follows one flow), and whether the real backend still answers in the shapes the AppTest fakes use. The backend's tests cover the backend's side of that contract.

#### Manual checks

Checked by hand in a browser against the running stack:

| Action | What the user sees |
|---|---|
| Stop the backend, then click anything | `Cannot reach the backend at http://127.0.0.1:8000. Start it (uv run fastapi dev in backend/), then try again.` No traceback; after the backend starts again, the next click loads the data and the user stays logged in |
| Sign up with `not-an-email` and a 5-character password | `Please fix: email: value is not a valid email address: ...; password: String should have at least 8 characters` |
| Add a task with an empty title | The Title field is marked as required, and nothing is sent |
| Log in with a wrong password | `Wrong email or password` |
| A second account | Sees none of the first account's courses or tasks; the API answers `404` for them |
| Stop the AI service, then **Update study plan** | `Couldn't create a new plan right now. Your previous plan is kept. Try again in a few minutes.` The saved plan stays on screen; **Technical details** says the AI service did not answer (503) |

Reloading the page logs the user out, because the login token lives in the browser tab's Streamlit session. Error messages therefore say "try again", not "reload".

`127.0.0.1` rather than `localhost`: on Windows, `localhost` tries IPv6 first and adds about 2 seconds to every request.

## AI service

`ai-service/` turns a user's unfinished tasks and free hours into a study plan. It is a separate process on port 8001 and stores nothing: the backend sends everything the plan needs and owns the saved plan (see [The study plan](#the-study-plan)).
Code builds a deterministic baseline plan first. A Pydantic AI agent may then rearrange the first week; code checks its proposal, and the baseline is the fallback.

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

### The model proposes, the code decides

An optional `note` in the request (up to 500 characters, such as "keep Thursday light") guides the model. The model sees the free hours, the tasks and the baseline, and returns only task ids and hours per day for the first week. It returns no free text, so it cannot invent chapters, topics or materials.

| The model may | Code enforces |
|---|---|
| Move hours between days and tasks within the week | Only this week's dates and plannable tasks, in half hours |
| Follow the user's note as a preference | A day's free hours, nothing on or after a due date, no more hours than a task needs |
| | Every task on time in the baseline stays on time, and the week keeps the baseline's total hours |

A proposal that breaks a rule goes back to the model with the reasons, at most twice. The note and task titles are data: an instruction inside them cannot change a rule, because the code checks the result whatever the model was told. Weeks 2 to 8 are always planned by the code, from the accepted week.

| In the response | Meaning |
|---|---|
| `source: "model"` | the model's week was accepted |
| `source: "baseline"`, no `fallback_reason` | nothing to arrange this week, so the model was not called |
| `source: "baseline"`, `fallback_reason` | the model was asked and the baseline was used: `invalid_output`, `budget_exceeded` (5 agent steps, 5 tool calls, 20,000 tokens), `timeout` or `provider_error` |

A failing model never fails the request: the caller always gets a valid plan, labelled honestly. Logs record the reason and the usage counters, never the user's tasks or note.

| Variable | Default | Purpose |
|---|---|---|
| `AI_MODEL` | `test` | the model, as `<provider>:<model>`. `test` is the built-in fake model: no key, no network, no cost. It proposes nothing valid, so plans come from the baseline with `fallback_reason: "invalid_output"` |
| `OLLAMA_BASE_URL` | none | where a local Ollama listens, such as `http://localhost:11434/v1`, for `AI_MODEL=ollama:<tag>` |
| `AI_TIMEOUT_SECONDS` | `25` | the wall-clock limit on the model; a local model may need more |

Settings go in a git-ignored `.env` at the repository root (`.env.example` lists them), used with `uv run --env-file ../.env fastapi dev --port 8001`. Only OpenAI-compatible providers are installed (`pydantic-ai-slim[openai]`), which includes Ollama.

`tests/test_agent.py` covers every rule and failure with `FunctionModel`, a scripted fake, and `tests/conftest.py` makes any real model call raise. These tests prove the wiring and the rules. They say nothing about the quality of a real model's plans: that is what the evaluation dataset will measure.

## Project layout

```
backend/
  app/
    main.py        routes and startup
    auth.py        accounts: password hashing, tokens, who is calling
    models.py      task table and request/response models with validation
    db.py          database engine and per-request session
    ordering.py    the urgency and by-course views
    queries.py     a user's courses and tasks, for the task routes and the plan
    planning.py    constraints and plan routes; what is sent and when a plan is outdated
    ai_contract.py the backend's copy of the AI service contract, and its checks on answers
    ai_client.py   the only HTTP client for the AI service: timeouts, errors, retries
  tests/           pytest tests; ai_openapi.json is the AI service's published schema
  scripts/demo_data.py  creates a demo account with sample data
  Dockerfile
frontend/
  streamlit_app.py the page Streamlit runs: loads data, picks a screen
  account.py       landing screen, log in, sign up, log out
  views.py         the screens: numbered list, and course cards with their tasks
  plan_view.py     Weekly study plan: the free time dialog, creating a plan, day cards, each task's planning line
  dialogs.py       pop-up forms: add/edit task, add/rename/delete course
  labels.py        names, icons and due-date wording
  texts.py         every interface text in English and Hebrew, and the current language
  api.py           every HTTP call to the backend, with user-facing error messages
  .streamlit/config.toml  theme: white and gold, Jost font, round buttons, 20 px base size
ai-service/
  app/
    main.py        /health and POST /plan
    schemas.py     the request and response contract, with validation
    planner.py     the deterministic plan, and the checks on the model's week
    agent.py       the Pydantic AI agent: instructions, tools, output validator
  tests/           pytest tests, including randomized checks of the rules
```

## AI-use note

Development was assisted by Claude (Claude Code). It drafted the project setup, models, routes, tests, Dockerfile, the Streamlit frontend and this README from my specifications.
I reviewed each change, ran the test suite (`uv run pytest`) and checked the API manually against a running server, including invalid input, missing records and persistence across restarts.
