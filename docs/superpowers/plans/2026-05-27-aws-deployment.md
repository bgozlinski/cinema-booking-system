# AWS Deployment & CI/CD Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize KinoMania and ship it to a single AWS EC2 box (nginx + gunicorn + Postgres via Docker Compose) behind Let's Encrypt TLS at `https://kinomaniak.bnbg.pl`, with a full GitHub Actions CD pipeline (build → GHCR → SSH deploy).

**Architecture:** One EC2 instance runs four compose services — `nginx` (TLS termination, static/media, reverse proxy), `web` (gunicorn, image pulled from GHCR), `db` (postgres:16), `certbot` (cert issue/renew). CI builds and pushes the image on every push to `main`, then SSHes into the box to pull and restart. nginx forwards `X-Forwarded-Proto: https`, which the existing `settings/prod.py` already trusts.

**Tech Stack:** Docker (multi-stage), Docker Compose v2, gunicorn, nginx, certbot/Let's Encrypt, GitHub Actions, GHCR, Poetry, Django 6 / Python 3.13.

**Spec:** `docs/superpowers/specs/2026-05-27-aws-deployment-design.md`

**Branch:** `infra/aws-deployment` (create before Task 1: `git checkout -b infra/aws-deployment`).

**Role split (per project convention):** Claude writes all infra/config files + all tests. The `/healthz` *view* and its URL wiring are app code (user implements). The user runs all `git`, `gh`, `poetry`, `docker`, AWS, DNS, and Stripe commands; Claude proposes them. Commit blocks below are proposals for the user to run.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `settings/base.py` | Modify | Add `STATIC_ROOT` (collectstatic target) |
| `settings/prod.py` | Modify | Add `CSRF_TRUSTED_ORIGINS` |
| `apps/cinema/views.py` | Modify | `/healthz` view (DB-probe liveness) |
| `settings/urls.py` | Modify | Wire `healthz` URL |
| `tests/test_security_settings.py` | Modify | Assert `STATIC_ROOT` + `CSRF_TRUSTED_ORIGINS` |
| `tests/test_healthz.py` | Create | `/healthz` returns 200 |
| `pyproject.toml` / `poetry.lock` | Modify | Add `gunicorn` |
| `.dockerignore` | Create | Trim build context |
| `deploy/entrypoint.sh` | Create | migrate → collectstatic → gunicorn |
| `Dockerfile` | Create | Multi-stage app image |
| `.env.prod.example` | Create | Prod env template |
| `.gitignore` | Modify | Un-ignore `.env.prod.example`, ignore `certbot/` + `backups/` |
| `deploy/nginx/default.conf` | Create | nginx :80 + :443 vhost |
| `docker-compose.prod.yml` | Create | 4-service prod stack |
| `deploy/init-letsencrypt.sh` | Create | First-cert bootstrap |
| `deploy/deploy.sh` | Create | pull + up + smoke check |
| `deploy/backup.sh` | Create | pg_dump + rotate |
| `.github/workflows/ci.yml` | Modify | hadolint, compose-validate, build-push, deploy jobs |
| `docs/deployment.md` | Create | Provisioning + go-live runbook |

---

## Phase 1 — Testable core (settings, healthz, deps)

### Task 1: Add `STATIC_ROOT` for collectstatic

**Files:**
- Modify: `settings/base.py` (Static section, ~line 108-111)
- Test: `tests/test_security_settings.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_security_settings.py`:

```python
def test_prod_has_static_root_for_collectstatic():
    prod = importlib.import_module("settings.prod")

    assert hasattr(prod, "STATIC_ROOT"), "STATIC_ROOT missing — collectstatic will fail"
    assert prod.STATIC_ROOT.name == "staticfiles"
    # STATIC_ROOT (collect target) must differ from the source dirs
    assert prod.STATIC_ROOT not in prod.STATICFILES_DIRS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_security_settings.py::test_prod_has_static_root_for_collectstatic -v`
Expected: FAIL with `AttributeError: module 'settings.prod' has no attribute 'STATIC_ROOT'`

- [ ] **Step 3: Add `STATIC_ROOT`** — in `settings/base.py`, in the `# ─── Static ───` block, immediately after the `STATICFILES_DIRS` line:

```python
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target (gitignored; nginx serves it)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_security_settings.py -v`
Expected: PASS (both old and new tests)

- [ ] **Step 5: Commit**

```bash
git add settings/base.py tests/test_security_settings.py
git commit -m "feat(infra): add STATIC_ROOT for production collectstatic

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Add `CSRF_TRUSTED_ORIGINS` to prod settings

**Files:**
- Modify: `settings/prod.py` (after the security block, ~line 35)
- Test: `tests/test_security_settings.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_security_settings.py`:

```python
def test_prod_trusts_the_deployment_origin_for_csrf():
    prod = importlib.import_module("settings.prod")

    assert "https://kinomaniak.bnbg.pl" in prod.CSRF_TRUSTED_ORIGINS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_security_settings.py::test_prod_trusts_the_deployment_origin_for_csrf -v`
Expected: FAIL with `AttributeError: ... has no attribute 'CSRF_TRUSTED_ORIGINS'`

- [ ] **Step 3: Add the setting** — in `settings/prod.py`, append after the `X_FRAME_OPTIONS = "DENY"` line:

```python
# Django 6 requires the deployment origin to be trusted for CSRF when POSTing
# from forms/admin behind a proxy; without this, every POST 403s. Comma-separated
# in .env (e.g. "https://kinomaniak.bnbg.pl").
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["https://kinomaniak.bnbg.pl"]
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_security_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add settings/prod.py tests/test_security_settings.py
git commit -m "feat(infra): trust deployment origin for CSRF in prod settings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: `/healthz` liveness endpoint

**Files:**
- Modify: `apps/cinema/views.py` (append view) — *user implements (app code)*
- Modify: `settings/urls.py` (wire URL) — *user implements*
- Test: `tests/test_healthz.py` (create) — *Claude writes*

- [ ] **Step 1: Write the failing test** — create `tests/test_healthz.py`:

```python
"""Deploy smoke-check probe: /healthz must report DB-backed liveness."""

import pytest


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_healthz.py -v`
Expected: FAIL with 404 (URL not wired) — `assert 404 == 200`

- [ ] **Step 3: Add the view** — append to `apps/cinema/views.py` (add the imports to the existing import block if not already present):

```python
from django.db import connection
from django.http import HttpRequest, JsonResponse


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness + DB-connectivity probe used by the deploy smoke check."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
```

- [ ] **Step 4: Wire the URL** — in `settings/urls.py`, add the import near the top and a path as the first entry in `urlpatterns`:

```python
from apps.cinema.views import healthz
```

```python
urlpatterns: list[URLPattern | URLResolver] = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    # ... existing entries unchanged ...
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `poetry run pytest tests/test_healthz.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/cinema/views.py settings/urls.py tests/test_healthz.py
git commit -m "feat(infra): add /healthz DB-liveness probe for deploy smoke check

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Add `gunicorn` dependency

**Files:**
- Modify: `pyproject.toml` (`[project].dependencies`)
- Modify: `poetry.lock` (regenerated)

- [ ] **Step 1: Add the dependency** — in `pyproject.toml`, add to the `dependencies` array (after `drf-spectacular`):

```toml
dependencies = [
    "django (>=6.0.4,<7.0.0)",
    "django-environ (>=0.13.0,<0.14.0)",
    "psycopg[binary] (>=3.3.4,<4.0.0)",
    "pillow (>=11.0,<12)",
    "stripe (>=15.1.0,<16.0.0)",
    "djangorestframework (>=3.17.1,<4.0.0)",
    "djangorestframework-simplejwt (>=5.5.1,<6.0.0)",
    "django-filter (>=25.2,<26.0)",
    "drf-spectacular (>=0.29.0,<0.30.0)",
    "gunicorn (>=23.0.0,<24.0.0)"
]
```

- [ ] **Step 2: Lock and install**

Run:
```bash
poetry lock
poetry install
```
Expected: lock resolves, `gunicorn` installed.

- [ ] **Step 3: Verify gunicorn is importable**

Run: `poetry run gunicorn --version`
Expected: prints `gunicorn (version 23.x.x)`

- [ ] **Step 4: Verify the suite still passes**

Run: `poetry run pytest -q`
Expected: all tests PASS (no regressions from the new dep).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "build(infra): add gunicorn as a production WSGI server

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Phase 2 — Containerization

### Task 5: `.dockerignore`

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```gitignore
# VCS / CI
.git
.github
.gitignore

# Python caches & envs
__pycache__/
*.py[cod]
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/

# Tests, coverage, docs (not needed in the runtime image)
**/tests/
htmlcov/
.coverage*
coverage.xml
docs/

# Local data & secrets
media/
staticfiles/
.env
.env.*
!.env.prod.example
db.sqlite3

# Compose / deploy host-side files & certs
docker-compose.override.yml
certbot/
backups/

# Editor / OS
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db

# Source .po catalogs — keep compiled .mo (committed) for runtime translations
locale/**/*.po

# Stripe CLI binary
stripe
stripe.exe
```

- [ ] **Step 2: Verify it parses** (Docker reads it lazily; just confirm the file exists and is non-empty)

Run: `wc -l .dockerignore`
Expected: prints a line count > 20.

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "build(infra): add .dockerignore to trim image build context

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Container entrypoint

**Files:**
- Create: `deploy/entrypoint.sh`

- [ ] **Step 1: Create `deploy/entrypoint.sh`**

```sh
#!/bin/sh
set -e

echo "### [entrypoint] Applying database migrations ..."
python manage.py migrate --noinput

echo "### [entrypoint] Collecting static files ..."
python manage.py collectstatic --noinput

echo "### [entrypoint] Starting gunicorn on :8000 ..."
exec gunicorn settings.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile -
```

- [ ] **Step 2: Mark executable** (so the git index records the +x bit on Linux)

Run: `chmod +x deploy/entrypoint.sh`
Expected: no output (exit 0).

- [ ] **Step 3: Commit**

```bash
git add deploy/entrypoint.sh
git update-index --chmod=+x deploy/entrypoint.sh
git commit -m "build(infra): add container entrypoint (migrate, collectstatic, gunicorn)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

> Note (Windows): `git update-index --chmod=+x` ensures the executable bit is stored even though NTFS doesn't track it. Verify with `git ls-files -s deploy/entrypoint.sh` → mode should be `100755`.

---

### Task 7: Multi-stage `Dockerfile` + build validation

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
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
```

- [ ] **Step 2: Lint with hadolint**

Run: `docker run --rm -i hadolint/hadolint < Dockerfile`
Expected: no output (clean). If a rule fires, fix it or add a targeted `# hadolint ignore=DLxxxx` above the offending line.

- [ ] **Step 3: Build the image**

Run: `docker build -t kinomania:local .`
Expected: build succeeds; final line `naming to docker.io/library/kinomania:local`.

- [ ] **Step 4: Validate prod config inside the built image**

Run:
```bash
docker run --rm \
  -e DJANGO_SETTINGS_MODULE=settings.prod \
  -e SECRET_KEY=ci-not-for-prod-0123456789abcdefghijklmnopqrstuvwxyz \
  -e DATABASE_URL=sqlite:///dummy.db \
  -e ALLOWED_HOSTS=kinomaniak.bnbg.pl \
  -e CSRF_TRUSTED_ORIGINS=https://kinomaniak.bnbg.pl \
  --entrypoint python \
  kinomania:local manage.py check --deploy --fail-level WARNING
```
Expected: `System check identified no issues (0 silenced).` (exit 0). The 50+ char `SECRET_KEY` avoids the `security.W009` warning.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile
git commit -m "build(infra): multi-stage Dockerfile for the production app image

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Phase 3 — Compose stack, nginx, TLS

### Task 8: Prod env template + `.gitignore` fix

**Files:**
- Create: `.env.prod.example`
- Modify: `.gitignore`

- [ ] **Step 1: Fix `.gitignore`** — the existing `.env.*` rule (with only `!.env.example`) would ignore the new template. Change the Environment block and add deploy artifacts:

```gitignore
# Environment
.env
.env.*
!.env.example
!.env.prod.example
```

And append a new block near the Docker section:

```gitignore
# Let's Encrypt certs + DB backups (created on the server at runtime)
certbot/
backups/
```

- [ ] **Step 2: Create `.env.prod.example`**

```bash
# ── Core ──────────────────────────────────────────────────────────────
# Generate SECRET_KEY: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=replace-with-a-64-char-random-secret
DEBUG=False
ALLOWED_HOSTS=kinomaniak.bnbg.pl
CSRF_TRUSTED_ORIGINS=https://kinomaniak.bnbg.pl
BASE_URL=https://kinomaniak.bnbg.pl
LANGUAGE_CODE=pl
TIME_ZONE=Europe/Warsaw

# ── Database (points at the `db` compose service; password MUST match) ──
POSTGRES_DB=kinomania
POSTGRES_USER=kinomania
POSTGRES_PASSWORD=replace-with-a-strong-password
DATABASE_URL=postgres://kinomania:replace-with-a-strong-password@db:5432/kinomania

# ── Email (Gmail SMTP — requires a 16-char Google App Password, NOT your
#    normal login password; 2-Step Verification must be enabled) ─────────
DEFAULT_FROM_EMAIL=your.address@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your.address@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password

# ── Stripe (TEST mode) ─────────────────────────────────────────────────
STRIPE_API_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# ── JWT / throttling (optional — base.py has sane defaults) ─────────────
JWT_ACCESS_TOKEN_LIFETIME_MIN=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7
THROTTLE_ANON=100/hour
THROTTLE_USER=1000/hour
THROTTLE_AUTH=20/hour
```

- [ ] **Step 3: Verify git will track the template**

Run: `git check-ignore -v .env.prod.example`
Expected: **no output** (exit 1) — meaning it is NOT ignored. If it prints a rule, the `!.env.prod.example` negation is missing.

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.prod.example
git commit -m "build(infra): add .env.prod template + un-ignore it; ignore certbot/backups

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: nginx vhost (`:80` ACME/redirect + `:443` proxy)

**Files:**
- Create: `deploy/nginx/default.conf`

- [ ] **Step 1: Create `deploy/nginx/default.conf`**

```nginx
upstream django {
    server web:8000;
}

# ── HTTP: serve ACME challenge, redirect everything else to HTTPS ──
server {
    listen 80;
    server_name kinomaniak.bnbg.pl;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# ── HTTPS: TLS termination + static/media + reverse proxy ──
server {
    listen 443 ssl;
    server_name kinomaniak.bnbg.pl;

    ssl_certificate     /etc/letsencrypt/live/kinomaniak.bnbg.pl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kinomaniak.bnbg.pl/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Movie posters / actor photos can be a few MB.
    client_max_body_size 10M;

    location /static/ {
        alias /app/staticfiles/;
        access_log off;
        expires 30d;
    }

    location /media/ {
        alias /app/media/;
        access_log off;
        expires 30d;
    }

    location / {
        proxy_pass         http://django;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_redirect     off;
    }
}
```

- [ ] **Step 2: Commit** (full validation happens in Task 11 once the cert paths exist)

```bash
git add deploy/nginx/default.conf
git commit -m "build(infra): add nginx vhost (TLS proxy + static/media + ACME)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: `docker-compose.prod.yml` + validation

**Files:**
- Create: `docker-compose.prod.yml`

- [ ] **Step 1: Create `docker-compose.prod.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    env_file: .env.prod
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    image: ghcr.io/bgozlinski/cinema-booking-system:latest
    restart: unless-stopped
    env_file: .env.prod
    expose:
      - "8000"
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      db:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - static_volume:/app/staticfiles:ro
      - media_volume:/app/media:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - web
    # Reload every 6h so renewed certs are picked up without a restart.
    command: "/bin/sh -c 'while :; do sleep 6h & wait $${!}; nginx -s reload; done & nginx -g \"daemon off;\"'"

  certbot:
    image: certbot/certbot
    restart: unless-stopped
    volumes:
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    # Attempt renewal every 12h (no-op until ~30 days before expiry).
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

volumes:
  pg_data:
  static_volume:
  media_volume:
```

> The `$${...}` are escaped so Compose passes a literal `${...}` into the container shell (where `.env.prod` has injected the vars). `certbot/` uses bind mounts (not named volumes) so the init script can manipulate certs from the host.

- [ ] **Step 2: Validate the compose file** (needs a `.env.prod` to satisfy `env_file`; use the template)

Run:
```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml config >/dev/null && echo "compose OK"
rm .env.prod
```
Expected: prints `compose OK` (and `.env.prod` is removed — it must never be committed).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "build(infra): production docker-compose stack (db, web, nginx, certbot)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: First-certificate bootstrap script

**Files:**
- Create: `deploy/init-letsencrypt.sh`

- [ ] **Step 1: Create `deploy/init-letsencrypt.sh`**

```sh
#!/bin/sh
# One-time Let's Encrypt bootstrap. Run on the EC2 box AFTER:
#   - the DNS A record kinomaniak.bnbg.pl -> Elastic IP resolves, and
#   - .env.prod exists in this directory.
set -e

domain="kinomaniak.bnbg.pl"
email="bartlomiej.gozlinski@gmail.com"   # LE expiry notices
rsa_key_size=4096
data_path="./certbot"
staging=0   # set to 1 to test against LE staging (avoids rate limits)

compose="docker compose -f docker-compose.prod.yml"

if [ -d "$data_path/conf/live/$domain" ]; then
  printf "Existing certificate for %s found. Replace it? (y/N) " "$domain"
  read -r decision
  if [ "$decision" != "y" ] && [ "$decision" != "Y" ]; then exit; fi
fi

# 1. Recommended TLS params referenced by nginx (options-ssl-nginx.conf, dhparams).
if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  mkdir -p "$data_path/conf"
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
    -o "$data_path/conf/options-ssl-nginx.conf"
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
    -o "$data_path/conf/ssl-dhparams.pem"
fi

# 2. Dummy self-signed cert so nginx can start its :443 block.
echo "### Creating dummy certificate ..."
live_path="/etc/letsencrypt/live/$domain"
mkdir -p "$data_path/conf/live/$domain"
$compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:1024 -days 1 \
    -keyout '$live_path/privkey.pem' \
    -out '$live_path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

# 3. Start nginx against the dummy cert.
echo "### Starting nginx ..."
$compose up --force-recreate -d nginx

# 4. Drop the dummy and request the real certificate over the webroot challenge.
echo "### Deleting dummy certificate ..."
$compose run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/$domain && \
  rm -Rf /etc/letsencrypt/archive/$domain && \
  rm -Rf /etc/letsencrypt/renewal/$domain.conf" certbot

echo "### Requesting Let's Encrypt certificate ..."
staging_arg=""
if [ "$staging" != "0" ]; then staging_arg="--staging"; fi
$compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email $email \
    -d $domain \
    --rsa-key-size $rsa_key_size \
    --agree-tos --no-eff-email --force-renewal" certbot

# 5. Reload nginx with the real cert.
echo "### Reloading nginx ..."
$compose exec nginx nginx -s reload
echo "### Done. https://$domain should now serve a valid certificate."
```

- [ ] **Step 2: Mark executable**

Run: `chmod +x deploy/init-letsencrypt.sh`

- [ ] **Step 3: Commit**

```bash
git add deploy/init-letsencrypt.sh
git update-index --chmod=+x deploy/init-letsencrypt.sh
git commit -m "build(infra): Let's Encrypt first-cert bootstrap script

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Phase 4 — CI/CD pipeline

### Task 12: CI hardening in the `quality` job

**Files:**
- Modify: `.github/workflows/ci.yml` (add steps to the `quality` job)

- [ ] **Step 1: Add hadolint + compose-validate steps** — at the end of the `quality` job's `steps:` (after the Bandit step):

```yaml
      - name: Hadolint (Dockerfile lint)
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile

      - name: Validate prod compose file
        run: |
          cp .env.prod.example .env.prod
          docker compose -f docker-compose.prod.yml config >/dev/null
          rm .env.prod
```

- [ ] **Step 2: Validate the workflow locally** (YAML well-formedness)

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml OK')"`
Expected: prints `yaml OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint Dockerfile (hadolint) and validate prod compose

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 13: `build-and-push` job → GHCR

**Files:**
- Modify: `.github/workflows/ci.yml` (add a new top-level job)

- [ ] **Step 1: Add the `build-and-push` job** — append after the `test` job:

```yaml
  build-and-push:
    name: Build & push image
    runs-on: ubuntu-latest
    needs: [quality, test]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Django deploy check (in built image)
        run: |
          docker run --rm \
            -e DJANGO_SETTINGS_MODULE=settings.prod \
            -e SECRET_KEY=ci-not-for-prod-0123456789abcdefghijklmnopqrstuvwxyz \
            -e DATABASE_URL=sqlite:///dummy.db \
            -e ALLOWED_HOSTS=kinomaniak.bnbg.pl \
            -e CSRF_TRUSTED_ORIGINS=https://kinomaniak.bnbg.pl \
            --entrypoint python \
            ghcr.io/${{ github.repository }}:${{ github.sha }} \
            manage.py check --deploy --fail-level WARNING
```

- [ ] **Step 2: Validate YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml OK')"`
Expected: `yaml OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: build and push image to GHCR on push to main

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

> Verification of the running job happens after the branch merges to `main` (Task 16 go-live). On a PR this job is skipped by the `if:` guard, which is expected.

---

### Task 14: `deploy` job + `deploy.sh`

**Files:**
- Create: `deploy/deploy.sh`
- Modify: `.github/workflows/ci.yml` (add the `deploy` job)

- [ ] **Step 1: Create `deploy/deploy.sh`**

```sh
#!/bin/sh
# Pull the latest image and restart the stack. Run from the repo root on EC2
# (the CD pipeline SSHes in and invokes this).
set -e
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"

echo "### Pulling latest web image ..."
$compose pull web

echo "### Restarting stack ..."
$compose up -d

echo "### Pruning dangling images ..."
docker image prune -f

echo "### Smoke check (https://kinomaniak.bnbg.pl/healthz) ..."
sleep 5
curl -fsS https://kinomaniak.bnbg.pl/healthz
echo ""
echo "### Deploy complete."
```

- [ ] **Step 2: Mark executable**

Run: `chmod +x deploy/deploy.sh`

- [ ] **Step 3: Add the `deploy` job** — append after `build-and-push`:

```yaml
  deploy:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    needs: build-and-push
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/kinomania
            ./deploy/deploy.sh
```

- [ ] **Step 4: Validate YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml OK')"`
Expected: `yaml OK`.

- [ ] **Step 5: Commit**

```bash
git add deploy/deploy.sh .github/workflows/ci.yml
git update-index --chmod=+x deploy/deploy.sh
git commit -m "ci: SSH-deploy to EC2 after image push (pull + restart + smoke check)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Phase 5 — Ops & runbook

### Task 15: Database backup script

**Files:**
- Create: `deploy/backup.sh`

- [ ] **Step 1: Create `deploy/backup.sh`**

```sh
#!/bin/sh
# Daily Postgres backup with rotation. Wire via cron (see docs/deployment.md).
set -e
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"
backup_dir="${BACKUP_DIR:-./backups}"
retention=7

mkdir -p "$backup_dir"

# Load POSTGRES_USER / POSTGRES_DB for pg_dump.
. ./.env.prod

timestamp=$(date +%Y%m%d-%H%M%S)
out="$backup_dir/kinomania-$timestamp.sql.gz"

echo "### Dumping database to $out ..."
$compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$out"

echo "### Rotating: keeping the $retention most recent backups ..."
ls -1t "$backup_dir"/kinomania-*.sql.gz | tail -n +$((retention + 1)) | xargs -r rm -f

echo "### Backup complete: $out"
```

- [ ] **Step 2: Mark executable**

Run: `chmod +x deploy/backup.sh`

- [ ] **Step 3: Commit**

```bash
git add deploy/backup.sh
git update-index --chmod=+x deploy/backup.sh
git commit -m "build(infra): daily pg_dump backup script with 7-day rotation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 16: Deployment runbook

**Files:**
- Create: `docs/deployment.md`

- [ ] **Step 1: Create `docs/deployment.md`**

````markdown
# KinoMania — Deployment Runbook

Production: **https://kinomaniak.bnbg.pl** · Single EC2 + Docker Compose
(nginx + gunicorn + Postgres), GHCR image, GitHub Actions CD.

## Architecture

nginx (TLS, static/media, reverse proxy) → gunicorn `web` (image from GHCR) →
`postgres` `db`. `certbot` issues/renews the Let's Encrypt cert. Only ports 80/443
are exposed. See `docs/superpowers/specs/2026-05-27-aws-deployment-design.md`.

## One-time provisioning

### 1. Launch EC2
- Ubuntu 24.04 LTS, **t3.small** (2 GB). On t3.micro (1 GB) add a 2 GB swapfile:
  ```bash
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
- Allocate an **Elastic IP** and associate it with the instance.
- **Security group** inbound: `22` (your IP only), `80` (0.0.0.0/0), `443` (0.0.0.0/0).

### 2. Install Docker
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out/in afterwards
```

### 3. Get the code + secrets onto the box
```bash
sudo mkdir -p /opt/kinomania && sudo chown $USER /opt/kinomania
git clone https://github.com/bgozlinski/cinema-booking-system.git /opt/kinomania
cd /opt/kinomania
cp .env.prod.example .env.prod
# Edit .env.prod: SECRET_KEY, POSTGRES_PASSWORD (+ matching DATABASE_URL),
# Gmail SMTP App Password, Stripe TEST keys.
nano .env.prod
```

### 4. Log in to GHCR (image is private)
Create a GitHub PAT (classic) with `read:packages`, then:
```bash
echo <PAT> | docker login ghcr.io -u bgozlinski --password-stdin
```

### 5. GitHub Actions secrets (repo → Settings → Secrets → Actions)
| Secret | Value |
|---|---|
| `SSH_HOST` | EC2 Elastic IP |
| `SSH_USER` | `ubuntu` |
| `SSH_PRIVATE_KEY` | Private key whose public half is in `~/.ssh/authorized_keys` on the box |

(GHCR push uses the built-in `GITHUB_TOKEN` — no secret needed.)

### 6. DNS
At the bnbg.pl registrar, add: **A** record, host `kinomaniak`, value `<Elastic IP>`,
TTL 300. Verify: `dig +short kinomaniak.bnbg.pl` → the Elastic IP.

### 7. Issue the first certificate
```bash
cd /opt/kinomania
./deploy/init-letsencrypt.sh        # set staging=1 inside first to dry-run
```

### 8. Bring up the full stack
```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # all healthy?
```
Create the admin user + demo data:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web python manage.py seed_db
```

### 9. Stripe webhook (TEST dashboard)
Add endpoint `https://kinomaniak.bnbg.pl/payments/webhooks/stripe/`, copy the
signing secret into `.env.prod` (`STRIPE_WEBHOOK_SECRET`), then:
```bash
docker compose -f docker-compose.prod.yml up -d web
```

### 10. Backup cron
```bash
crontab -e
# Daily 03:00 backup:
0 3 * * * cd /opt/kinomania && ./deploy/backup.sh >> /var/log/kinomania-backup.log 2>&1
```

## Continuous deployment
Push to `main` → CI runs `quality` + `test` → `build-and-push` (GHCR) →
`deploy` (SSH: `deploy/deploy.sh` pulls + restarts + curls `/healthz`).
Watch under the repo's **Actions** tab.

## Manual operations
| Task | Command (from `/opt/kinomania`) |
|---|---|
| Logs | `docker compose -f docker-compose.prod.yml logs -f web` |
| Restart | `docker compose -f docker-compose.prod.yml restart web` |
| Migrate | `docker compose -f docker-compose.prod.yml exec web python manage.py migrate` |
| Shell | `docker compose -f docker-compose.prod.yml exec web python manage.py shell` |
| Manual deploy | `./deploy/deploy.sh` |
| Backup now | `./deploy/backup.sh` |
| Restore | `gunzip -c backups/<file>.sql.gz \| docker compose -f docker-compose.prod.yml exec -T db psql -U kinomania kinomania` |

## Troubleshooting
- **502 from nginx** — `web` not up/healthy: check `docker compose ... logs web`.
- **CSRF 403 on POST** — `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` wrong in `.env.prod`.
- **Cert errors** — DNS must resolve to the EIP before `init-letsencrypt.sh`; re-run after fixing.
- **Static 404** — confirm `web` ran `collectstatic` (entrypoint logs) and `static_volume` is shared with nginx.
- **GHCR pull denied on deploy** — re-run `docker login ghcr.io` on the box (PAT expired).
````

- [ ] **Step 2: Commit**

```bash
git add docs/deployment.md
git commit -m "docs(infra): AWS deployment + go-live runbook

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Final verification (after merge to `main`, on the box)

- [ ] CI is green on the PR (quality incl. hadolint + compose-validate; test).
- [ ] On merge to `main`: `build-and-push` pushes `ghcr.io/bgozlinski/cinema-booking-system:latest`, and `deploy` succeeds (Actions log shows the `/healthz` curl returning `{"status": "ok"}`).
- [ ] `https://kinomaniak.bnbg.pl` loads over a valid certificate (padlock).
- [ ] Register a new account → activation email arrives via Gmail SMTP → log in.
- [ ] Complete a TEST-mode Stripe booking; confirm the webhook fires (booking → CONFIRMED).
- [ ] `/api/v1/docs/` and `/admin/` load and are styled (static served by nginx).
- [ ] `dig +short kinomaniak.bnbg.pl` returns the Elastic IP.
- [ ] `./deploy/backup.sh` writes a `.sql.gz` into `backups/`.

## Suggested PR boundaries
If splitting into smaller PRs: **PR1** Phase 1 (Tasks 1-4, app-level, fully testable in CI),
**PR2** Phases 2-3 (Tasks 5-11, Docker + compose + nginx + TLS), **PR3** Phases 4-5
(Tasks 12-16, CI/CD + ops + runbook). Phase 1 is independently safe to merge.
