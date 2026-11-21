# Smart Study Planner: project context for Claude

EASS course project (software engineering). Students track exams, assignments and projects per course; EX3 adds an AI study planner.

## Permanent instructions

### Language and wording

- Chat with the user in Hebrew, including short progress lines. The product stays in English: UI, code, comments, commits, PRs, README. The UI also offers Hebrew through `frontend/texts.py`.
- App users can be of any gender: write "they/their" in English, and plural or generic forms in Hebrew.

### Workflow

- Course repo (private) is remote `origin`; a public personal copy is remote `personal`. `origin` has two push URLs, so `git push` updates both repos.
- Every change goes through **Issue → branch → PR**. The user reviews and merges, with a merge commit. Never merge for the user.
- After a merge: `git switch main && git pull && git push`, so the personal repo gets the merge, then delete the merged branch.
- Before pushing more commits to an existing PR, check `gh pr view N --json state`. If it is already merged, open a follow-up PR.
- The local site is served from the checked-out branch. Switch to an up-to-date `main` and restart the servers before judging the UI. The repo is sometimes changed outside Claude.
- Force-pushes, and deleting branches that were never merged, need the user's explicit approval.
- After each finished step, append a Hebrew section to `notes/defense-notes.md`: what was done, files, commands, how it was verified, and likely defense questions. The notes are private study material for the oral defense.
- Git-ignored, never committed: `notes/`, `backend/data/`, `.claude/`. Add `.env` to `.gitignore` before any API key exists.

### Architecture

```
backend/   FastAPI + SQLModel + SQLite, port 8000
  app/main.py      /health, /courses CRUD, /tasks CRUD, /tasks/by-course
  app/auth.py      /auth/signup, /login (bearer token), /logout, /me (GET, PATCH language)
  app/models.py    User, AuthToken, Course, Task, and request/response models
  app/db.py        engine, get_session, ADDED_COLUMNS (adds new columns at startup)
  app/ordering.py  urgency order and by-course grouping
  app/queries.py   a user's courses and tasks (shared by task and plan routes)
  app/planning.py  /constraints (GET, PUT), /plan (POST builds via the AI service, GET reads + outdated)
  app/ai_contract.py, ai_client.py  backend copy of the AI contract + answer checks; httpx client, retries
  tests/ai_openapi.json  AI service schema snapshot for test_contract.py (regenerate after contract changes)
  scripts/demo_data.py  creates a demo account with sample data (idempotent)
frontend/  Streamlit, port 8501
  streamlit_app.py  landing or app screen, theme CSS, right-to-left in Hebrew
  account.py        landing, log in/sign up/log out, language switch (saved to the account)
  views.py          numbered list by urgency; course cards (3 per row) with their tasks
  plan_view.py      Weekly study plan (switch: Tasks and exams | Weekly study plan): free time dialog, create/update, day cards, planning lines
  dialogs.py        dialogs driven by session_state["dialog"] and on_dismiss
  labels.py, texts.py  task wording; every UI text in en and he; error translation
  api.py            the only HTTP client (httpx); every error carries a code
ai-service/  FastAPI, port 8001, stores nothing (EX3)
  app/schemas.py   POST /plan contract: start_date, constraints, tasks -> days, assessments
  app/planner.py   deterministic baseline: half-hour units, Moore-Hodgson, least slack first; proposal_problems checks the model's week
  app/agent.py     Pydantic AI agent (AI_MODEL, test by default): task ids and hours only, no free text
.github/workflows/ci.yml  per service: uv sync --locked, ruff check, ruff format --check, pytest; advisory uv audit
```

### Design decisions

- Task types: `exam`, `submission`, `online_quiz`, `homework`, `project`. Exams have `location` but no `status` and no `link`. An exam's status is **computed**: `todo` until its date passes, then `past` (never `done`). `estimated_hours` is optional for every type.
- PATCH merges the stored task with the changes and re-validates with `TaskCreate`. Sending `null` clears an optional field; a status sent for an exam gets 422.
- Courses are a table, with names unique per user ignoring case (409). A course that still has tasks cannot be deleted (409). Another user's data answers **404**, not 403.
- Dates are stored as local naive time (`to_local_time`, with an optional `zone` for tests). Docker sets `TZ=Asia/Jerusalem`. The repeated autumn DST hour is a known, tested limit.
- Passwords use salted scrypt; tokens are stored as sha256 hashes and expire after 14 days. The token lives in Streamlit `session_state`, so refreshing the page logs the user out (known limit; a cookie could fix it).
- `User.language` is stored as plain text (`en` or `he`). An enum column stores member *names*, which broke a migrated database.
- Plan (`ai-service`): the due day is never planned, whatever the time due. `all_fit` is true only if every task sent is `on_track`; a task with no estimate, overdue or later makes it false. A block is allocated hours, not a validated study session (no start time, length or break rules).
- Backend plan flow: `POST /plan` sends unfinished tasks + constraints to the AI service, checks the answer itself, then saves it (one plan per user); a failure keeps the old plan. 503 = unavailable (retried 3x for connect/timeout/503/504 only), 502 = invalid output. `GET /plan` never calls the AI; `outdated` when inputs changed or the first day passed.
- The model may only rearrange the first week; weeks 2 to 8 are always code. Any model failure returns the baseline with `fallback_reason`, never an error. Logs hold no user text.
- UI: white and gold theme in `frontend/.streamlit/config.toml` (Jost font, `baseFontSize = 20`, and Streamlit accepts only one font URL). In Hebrew: right-to-left marks around line separators; dates, times, toggles and switches stay left to right; the top bar keeps the same layout as English (the email and Log out on the left, the language on the right). The landing content is vertically centered (`st-key-landing-content`).
- Screens (agreed with the user): one primary action per screen, no duplicate buttons, short text only where needed, details on demand. Hebrew uses "מטלה" ("מטלות ומבחנים" for both). Plan wording is about planned study time ("in the plan"), never work done; the "out of date" note is general because the backend only returns a yes/no.

### EASS requirements

- EX1 (backend, due 2026-11-09): CRUD with Pydantic validation, persistence, tests, Dockerfile, README.
- EX2 (frontend, due 2026-11-30): a UI connected to EX1, error states, an automated UI flow, run instructions.
- EX3 (due 2027-01-11): an independent AI service (Pydantic AI), Docker Compose, data initialization, failure tests, basic CI, an AI evaluation dataset with results, a demo and a runbook.
- Also due 2027-01-11: 3 merged PRs to upstream repos with more than 10k stars (the user writes all maintainer-facing text), and an individual oral defense.
- Course material: `EASS-PART-A-2026-X/lecture-notes` (lectures/, guides/submission-evidence.md).

### Commands

```bash
cd backend && python -m uv run fastapi dev app/main.py         # API, docs at /docs
cd frontend && python -m uv run streamlit run streamlit_app.py
python -m uv run pytest                                         # in backend/ or frontend/
python -m uv run ruff check . && python -m uv run ruff format --check .
cd backend && python -m uv run python scripts/demo_data.py      # demo account (password in the script)
cd backend && docker build -t smart-study-planner . && docker run -d --name planner -p 127.0.0.1:8000:8000 -v planner-data:/app/data smart-study-planner
```

## Current state: check it, don't assume it

```bash
git branch --show-current && git status --short
gh pr list --state open && gh issue list --state open
gh run list --branch main --workflow CI --limit 1
git fetch --all && git rev-parse origin/main personal/main   # both repos in sync?
```

Progress at the time of writing (check against the repo):
- EX1 and EX2 are done.
- EX3 is in progress, one step per PR (see the plan below). Steps 1-3 are merged; check the open PRs for later steps.
- The upstream PRs have not started.

## EX3 plan (agreed with the user)

One Issue and PR per step:
1. `ai-service/` (FastAPI, port 8001), deterministic part first: free hours per day from the user's constraints (weekly free hours per weekday, blocked dates); a feasibility check per task; a baseline plan; a CI entry.
2. A Pydantic AI agent (`AI_MODEL`, `test` by default; Ollama locally, so ask before pulling a model; a paid API is optional). The model proposes and code enforces. Limited `ModelRetry`; fall back to the baseline plan.
3. Backend: a constraints table, `POST /plan` (calls the AI service, saves the plan) and `GET /plan`; a calm message when the AI service is down.
4. Frontend: a "My plan" screen and a constraints screen.
5. Docker Compose with all three services, demo data at startup, a compose job in CI.
6. Product analytics with PostHog (lecturer's announcement, Nov 2026): anonymous events only (signed up, task added, plan built, ...), never emails, titles or the note; the key comes from `.env`, and with no key nothing is sent, so tests and CI make no network calls. The user creates the PostHog account.
7. An AI evaluation dataset (10–15 scenarios) with results.
8. Free public deployment (lecturer's announcement, Nov 2026). Choose the platform only when this step starts, after checking each provider's current pricing page: free tiers change often. Needs: all three services, data that survives restarts, secrets outside Git, and the AI service reachable only by the backend. Options found in Nov 2026: a free VM running the Compose stack (Oracle Cloud Always Free), or free container hosting that sleeps when idle plus a free managed Postgres (Render + Neon), which means moving from SQLite to Postgres. The user creates the accounts.
9. A runbook, the release tags (`v1.0.0-rc.1`, then `v1.0.0` on a green commit), the live demo, and the required English-narrated product video (about 5 minutes, the user's own voice, linked from the README and the submission).

Planner rules from the user:
- Produce feasible and best-effort plans, and report shortfalls honestly. Estimated hours are estimates, not guarantees.
- Never invent chapters, topics or materials.
- Plan 7 days in detail, looking up to 8 weeks ahead.
- Hard constraints are structured data enforced in code; the free-text note guides the model but cannot override them.
- Never double-book the same hours.
- Prioritize by slack: the free hours before the deadline minus the hours needed, not only the earliest deadline.
- Rebuild the plan only when the user asks, and show when it is outdated.

Later ideas: keep the login across a page refresh (cookie); grades and credits per course.
