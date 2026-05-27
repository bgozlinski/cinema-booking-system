# AWS Deployment & CI/CD Hardening — KinoMania

- **Phase:** Post-`v1.0.0` infrastructure (beyond the M1–M5 backlog)
- **Type:** Infra/DevOps · **Size:** L
- **Branch:** `infra/aws-deployment` (single feature branch; plan may split into sub-PRs)
- **Date:** 2026-05-27
- **Target:** Live deployment at `https://kinomaniak.bnbg.pl`

## Goal

Take the finished KinoMania app from "runs locally" to "running in production on
AWS, with automated deploys." Containerize the Django app, run it on a single EC2
instance via Docker Compose (app + nginx + Postgres), terminate TLS with nginx +
Let's Encrypt, and extend the existing CI to a full continuous-deployment pipeline:
push to `main` → build image → push to GHCR → SSH deploy to EC2 → restart + smoke
check.

This is a learning-grade project. The value is as much in standing up the *whole
real stack the manual way* (Docker, gunicorn, nginx, certbot, GHCR, SSH-based CD)
as in the running site itself. We deliberately avoid managed abstractions
(ECS/Fargate/RDS/IaC) to keep the moving parts visible and the cost near-zero.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Compute | Single EC2 + Docker Compose | Cheapest, full-stack learning, fits a single subdomain |
| Database | `postgres:16` container on the box + `pg_dump` backups | Self-contained, zero extra AWS cost, mirrors dev |
| CI/CD | Full CD: build → GHCR → SSH deploy → restart | Complete hands-off pipeline; most to learn |
| Registry | GitHub Container Registry (`ghcr.io`) | Native to GitHub Actions, free at this scale |
| Deploy trigger | SSH from GitHub Actions (`appleboy/ssh-action`) | Transparent, debuggable, visible in Actions log |
| TLS | nginx + Let's Encrypt (certbot, webroot challenge) | Free certs, standard pattern, fits nginx-on-box |
| DNS | Registrar-managed A record → EC2 Elastic IP | No AWS DNS cost; user owns the record |
| Stripe | Test mode (`sk_test_` / test webhook) | Portfolio/demo deploy; no real money |
| Email | Gmail SMTP (App Password) | User's private Gmail; enables real activation flow |
| CI hardening | hadolint + `compose config` + in-image `check --deploy` | Directly serves the "CI hardening" goal; cheap |

## Architecture

```
                    Internet
                       │
            kinomaniak.bnbg.pl  (A record → Elastic IP)
                       │
            ┌──────────▼───────────────────────────────┐
            │  EC2 (Ubuntu 24.04 LTS, t3.small, EIP)    │
            │  Security group: 22 (your IP), 80, 443    │
            │                                            │
            │   docker compose -f docker-compose.prod    │
            │  ┌──────────┐   ┌──────────┐   ┌────────┐  │
            │  │  nginx   │──▶│   web    │──▶│   db   │  │
            │  │ :80 :443 │   │ gunicorn │   │postgres│  │
            │  │  TLS     │   │  :8000   │   │ :5432  │  │
            │  └────┬─────┘   └────┬─────┘   └───┬────┘  │
            │       │ serves       │ writes      │       │
            │   static_volume ◀────┘         pg_data     │
            │   media_volume  ◀────┘     (+ daily pg_dump)│
            │   certbot_certs / certbot_www              │
            └────────────────────────────────────────────┘
                       ▲
                       │ SSH deploy (GitHub Actions)
                       │ docker pull ghcr.io/bgozlinski/cinema-booking-system
              GitHub Actions CI/CD  ──build/push──▶  GHCR
```

**Request flow:** nginx terminates TLS, serves `/static/` + `/media/` directly from
shared volumes, and reverse-proxies everything else to gunicorn on `web:8000` with
`X-Forwarded-Proto: https`. The existing `SECURE_PROXY_SSL_HEADER` in `settings/prod.py`
already trusts that header, so Django correctly treats requests as secure. Only nginx's
`80`/`443` are published to the host; `web` and `db` are reachable only on the internal
compose network.

## Scope

### In scope

**App containerization**
1. Multi-stage `Dockerfile` — Poetry builder stage (`--only main`) → slim runtime stage,
   non-root user, `DJANGO_SETTINGS_MODULE=settings.prod`.
2. `.dockerignore` — exclude `.git`, `**/tests`, `.venv`, `media`, `htmlcov`,
   `docs`, `locale/**/*.po` (keep compiled `.mo`), local `.env*`.
3. Add `gunicorn` to `[project].dependencies` in `pyproject.toml`.
4. `deploy/entrypoint.sh` — on container start: `migrate --noinput` → `collectstatic --noinput`
   → `exec gunicorn settings.wsgi:application --bind 0.0.0.0:8000 --workers 3`.
   (Single instance ⇒ entrypoint-migrate is safe and self-healing.)

**Settings & app changes** (minimal, prod-scoped)
5. `STATIC_ROOT = BASE_DIR / "staticfiles"` in `settings/base.py` — currently **missing**;
   `collectstatic` fails without it. Distinct from the `static/` source dir
   (`STATICFILES_DIRS`).
6. `CSRF_TRUSTED_ORIGINS` in `settings/prod.py` (env-driven, defaulting to
   `["https://kinomaniak.bnbg.pl"]`) — **required**, or admin/login/booking POSTs fail
   CSRF behind the proxy on Django 6.
7. `/healthz` view returning HTTP 200 (lightweight, optionally a `SELECT 1` DB check) —
   deploy smoke-test target. *App code: user implements; Claude writes the test.*

**Compose & nginx**
8. `docker-compose.prod.yml` — services `db`, `web`, `nginx`, `certbot` (table below).
   `restart: unless-stopped` on long-running services; `web`/`db` not published to host.
9. `deploy/nginx/` — `:80` server (ACME challenge + HTTPS redirect) and `:443` server
   (TLS, `/static/`, `/media/`, `proxy_pass` to `web:8000`, bumped `client_max_body_size`
   for poster/photo uploads).

**TLS automation**
10. `deploy/init-letsencrypt.sh` — one-time first-issuance (nginx HTTP-only → webroot
    challenge → enable `:443`).
11. Auto-renewal — `certbot` service loops `certbot renew` every 12h; nginx reloads every 6h.

**CI/CD** (extend `.github/workflows/ci.yml`)
12. Keep `quality` + `test` unchanged.
13. `build-and-push` job (`needs: [quality, test]`, gated to `push` on `main`): GHCR login
    via built-in `GITHUB_TOKEN`, `docker/build-push-action` with layer caching, tags
    `:latest` + `:<sha>`.
14. `deploy` job (`needs: build-and-push`): `appleboy/ssh-action` runs `deploy/deploy.sh`
    on EC2 (`docker compose -f docker-compose.prod.yml pull web && up -d`), then
    `curl -f https://kinomaniak.bnbg.pl/healthz` as a post-deploy gate.
15. CI hardening in `quality`: `hadolint` (Dockerfile lint), `docker compose -f
    docker-compose.prod.yml config` (compose validation), and `manage.py check --deploy
    --settings=settings.prod` run inside the freshly built image.

**Ops scripts & config**
16. `deploy/deploy.sh` — pull + up + prune (idempotent).
17. `deploy/backup.sh` — `pg_dump | gzip` to `/opt/kinomania/backups/`, rotate (keep 7).
    Wired via documented host cron.
18. `.env.prod.example` — full prod env template (incl. Gmail SMTP slots, App-Password note).
19. `docs/deployment.md` — provisioning + go-live runbook (manual steps).

**Tests** (Claude-authored)
20. Extend `tests/test_security_settings.py`: assert `STATIC_ROOT` set and
    `CSRF_TRUSTED_ORIGINS` includes the prod origin under `settings.prod`.
21. `test_healthz` — `/healthz` returns 200.

### Out of scope (YAGNI / future)
- Terraform / CloudFormation IaC (one box → documented runbook instead).
- RDS, ECS/Fargate, ALB, Route 53, ACM.
- S3 backup offload (local rotation only; noted as a future step).
- Multi-instance / autoscaling / zero-downtime rolling deploys.
- WhiteNoise (nginx serves static, so unnecessary).
- CDN / object storage for media.

## Compose service matrix (`docker-compose.prod.yml`)

| Service | Image | Role | Ports | Volumes |
|---|---|---|---|---|
| `db` | `postgres:16-alpine` | database | internal only | `pg_data` |
| `web` | `ghcr.io/bgozlinski/cinema-booking-system:latest` | gunicorn app | internal `:8000` | `static_volume`, `media_volume` (rw) |
| `nginx` | `nginx:alpine` | TLS + reverse proxy + static/media | `80:80`, `443:443` | `static_volume`, `media_volume` (ro), `certbot_certs`, `certbot_www` |
| `certbot` | `certbot/certbot` | cert issue + auto-renew | none | `certbot_certs`, `certbot_www` |

- `web` and `db` both read credentials from `env_file: .env.prod` (no hardcoded prod
  password, unlike the dev `docker-compose.yml`).
- `web` `depends_on: db` with `condition: service_healthy`.
- Dev `docker-compose.yml` / `docker-compose.override.yml` remain **untouched** (local DB).

## Infrastructure (EC2)

- **Instance:** Ubuntu 24.04 LTS, **t3.small (2 GB RAM)** — recommended over t3.micro
  (1 GB), which risks OOM with Postgres + gunicorn + nginx co-resident. Runbook notes a
  t3.micro fallback with a swapfile if budget demands.
- **Elastic IP** attached (stable DNS target across reboots).
- **Security group:** inbound `22` restricted to the user's IP, `80` + `443` open; outbound open.
- **Provisioning:** documented runbook — install Docker Engine + compose plugin, create
  `/opt/kinomania`, place compose/nginx/`.env.prod`, `docker login ghcr.io`, run
  `init-letsencrypt.sh`.

## Secrets

**On the box — `.env.prod`** (gitignored, never committed):
`SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=kinomaniak.bnbg.pl`,
`CSRF_TRUSTED_ORIGINS=https://kinomaniak.bnbg.pl`,
`DATABASE_URL=postgres://kinomania:<pw>@db:5432/kinomania`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `STRIPE_API_KEY` (test), `STRIPE_WEBHOOK_SECRET`
(test), `BASE_URL=https://kinomaniak.bnbg.pl`, `LANGUAGE_CODE`, `TIME_ZONE`,
`DEFAULT_FROM_EMAIL`, and Gmail SMTP: `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`,
`EMAIL_USE_TLS=True`, `EMAIL_HOST_USER=<gmail>`, `EMAIL_HOST_PASSWORD=<16-char App Password>`.

> **Gmail note:** SMTP requires a Google **App Password** (2-Step Verification must be
> enabled). The regular account password will not authenticate.

**In GitHub Actions secrets:** `SSH_PRIVATE_KEY`, `SSH_HOST` (Elastic IP), `SSH_USER`.
GHCR uses the auto-provided `GITHUB_TOKEN` — no manual registry secret.

## Manual steps (documented in `docs/deployment.md`)

1. Launch EC2 (Ubuntu 24.04, t3.small), attach Elastic IP, configure security group.
2. Install Docker Engine + compose plugin.
3. `git`/`scp` the deploy files to `/opt/kinomania`; create `.env.prod`.
4. `docker login ghcr.io` on the box (read-only PAT).
5. Add GitHub Actions secrets (`SSH_PRIVATE_KEY`, `SSH_HOST`, `SSH_USER`).
6. **DNS:** add A record `kinomaniak` → `<Elastic IP>`, TTL 300 for go-live.
7. Run `deploy/init-letsencrypt.sh` to issue the first cert.
8. **Stripe (test dashboard):** register webhook
   `https://kinomaniak.bnbg.pl/payments/webhooks/stripe/`; copy signing secret into `.env.prod`.
9. Install the backup cron (`deploy/backup.sh`).

## Testing & verification strategy

Infra files (Dockerfile/compose/nginx) are not pytest-testable; the verification chain is:

- **CI:** image builds (proves Dockerfile), `hadolint`, `compose config`, and
  `check --deploy` inside the image (catches prod-config regressions pre-deploy).
- **Deploy gate:** post-deploy `curl -f .../healthz` fails the job if the app didn't start.
- **pytest:** prod-settings assertions (`STATIC_ROOT`, `CSRF_TRUSTED_ORIGINS`) + `/healthz`
  view test.
- **Manual smoke (go-live):** browse the site over HTTPS, register → receive activation
  email → log in, complete a test-mode Stripe booking, confirm webhook fires, load
  `/api/v1/` docs, hit `/admin/`.

## Role split (per project convention)

- **Claude writes:** Dockerfile, `.dockerignore`, compose, nginx config, all `deploy/*.sh`
  scripts, CI/CD workflow edits, `.env.prod.example`, `docs/deployment.md`, settings edits
  (`STATIC_ROOT`, `CSRF_TRUSTED_ORIGINS`), and **all tests**. (Infra config is not "app
  code"; the `/healthz` *view* is the one piece of app logic — user implements, Claude tests.)
- **User runs:** all `git`/`gh` commands, all AWS console/CLI actions, EC2 provisioning,
  DNS, Stripe dashboard, and the on-box manual steps above.

## Risks & notes

- **t3.micro OOM** — mitigated by recommending t3.small (swapfile fallback documented).
- **First-cert chicken-and-egg** — `init-letsencrypt.sh` handles HTTP-only bootstrap before
  the `:443` block exists.
- **Entrypoint migrate on a single instance** — safe; would need rework only if scaled to
  multiple `web` replicas (out of scope).
- **CSRF behind proxy** — `CSRF_TRUSTED_ORIGINS` is mandatory on Django 6; omission is a
  classic post-deploy 403 footgun, called out explicitly.
- **DNS propagation** — keep TTL low for go-live; cert issuance must wait until the A
  record resolves to the Elastic IP.
- **GHCR image visibility** — default private; the box PAT (or making the package public)
  must allow pulls.
