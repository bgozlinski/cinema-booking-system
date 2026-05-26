# Security Review — KinoMania (US-42)

**Date:** 2026-05-26 · **Branch:** `chore/M5-security-review` · **Scope:** full codebase (`apps/`, `settings/`, config)

## Tools

| Tool | Command |
|---|---|
| bandit `1.9.4` | `poetry run bandit -c pyproject.toml -r apps settings` |
| Django deploy check | `python manage.py check --deploy --settings=settings.prod` |
| Manual review | secrets handling, CSRF coverage, Stripe webhook |

## Findings

| Area | Result | Notes |
|---|---|---|
| Secrets hygiene | PASS | `.env` + `.env.*` gitignored and untracked; no hardcoded `sk_`/`whsec_` literals in `apps/`/`settings/`; `detect-private-key` pre-commit hook present |
| CSRF coverage | PASS | Standard Django `CsrfViewMiddleware`; the sole `csrf_exempt` is the Stripe webhook (justified — see below) |
| Stripe webhook | PASS | `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)` verifies the signature before processing; idempotent via `StripeEvent.get_or_create`; `select_for_update` row lock |
| bandit static analysis | PASS | First run: 21 × `B311` (Low severity), all in `apps/cinema/management/commands/seed_db.py`. Triaged as false-positive (non-crypto demo seeding) → `skips = ["B311"]`. Re-run: **No issues identified.** |
| Deploy hardening | FIXED | `check --deploy`: **4 warnings → 0**. `settings/prod.py` now sets SSL redirect, secure cookies, HSTS, and defense-in-depth headers |

## Deploy check: before → after

**Before** (`settings/prod.py` had only `DEBUG=False` + email config):

```
System check identified some issues:

WARNINGS:
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting. ...
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True. ...
?: (security.W012) SESSION_COOKIE_SECURE is not set to True. ...
?: (security.W016) You have 'django.middleware.csrf.CsrfViewMiddleware' in your MIDDLEWARE, but you have not set CSRF_COOKIE_SECURE to True. ...

System check identified 4 issues (0 silenced).
```

**After** (hardening block added to `settings/prod.py`):

```
System check identified no issues (0 silenced).
```

Settings added (prod-only — `dev`/test profiles untouched): `SECURE_PROXY_SSL_HEADER`,
`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
`SECURE_HSTS_SECONDS` (1 year), `SECURE_HSTS_INCLUDE_SUBDOMAINS`,
`SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS = "DENY"`.
A regression test (`tests/test_security_settings.py`) asserts each value so the
hardening cannot silently regress.

## Justified exemptions

- **`apps/payments/views.py::stripe_webhook` — `@csrf_exempt`:** Stripe posts
  server-to-server, so CSRF tokens do not apply; authenticity is instead enforced
  by HMAC signature verification (`construct_event` with `STRIPE_WEBHOOK_SECRET`).
  Removing the exemption would break legitimate webhooks without adding security.
- **bandit `B311` skipped project-wide:** the check flags the stdlib `random`
  module wholesale. The only use is non-cryptographic demo-data seeding in
  `seed_db.py` (no tokens/passwords/crypto); `random` appears nowhere else in
  `apps/`/`settings/`. Documented in `[tool.bandit]` in `pyproject.toml`.

## Continuous enforcement

- **bandit** runs in CI as a step in the `quality` job (`.github/workflows/ci.yml`),
  alongside ruff and mypy — a new finding now fails the build.

## Out of scope (future NFR)

- Dependency CVE scanning (`pip-audit` / `safety`).
- Real deployment wiring (TLS certificates, runtime proxy configuration).
- A public vulnerability-reporting policy (root `SECURITY.md`).
