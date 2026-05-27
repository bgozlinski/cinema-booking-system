# syntax=docker/dockerfile:1

# ──────────────────────────── Builder ────────────────────────────
FROM python:3.13-slim AS builder

ENV POETRY_VERSION=2.1.4 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Only the dependency manifests — keeps this layer cached across code changes.
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# ──────────────────────────── Runtime ────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=settings.prod \
    PATH="/app/.venv/bin:$PATH"

# Non-root runtime user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Virtualenv from the builder (psycopg[binary] bundles libpq — no apt needed).
COPY --from=builder /app/.venv /app/.venv

# Application source.
COPY . .

# Volume mount points must exist and be owned by `app` so the named volumes
# inherit that ownership on first mount (collectstatic writes here as non-root).
RUN mkdir -p /app/staticfiles /app/media \
    && chmod +x deploy/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000
ENTRYPOINT ["deploy/entrypoint.sh"]
