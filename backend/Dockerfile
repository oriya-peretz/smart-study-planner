# syntax=docker/dockerfile:1
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jerusalem
WORKDIR /app

# 1) Dependencies only: cached until uv.lock changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# 2) Application code.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# 3) Never run as root. /app/data holds the SQLite volume.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown appuser /app/data
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
