# US-42 — Security review (bandit, CSRF coverage, secrets audit)

- **Milestone:** M5 — Security & i18n polish (`v1.0.0`)
- **Type:** NFR · **Size:** S · **Branch:** `chore/M5-security-review`
- **Backlog:** "Security review (bandit run, csrf coverage, secrets audit)"
- **Date:** 2026-05-26

## Goal

Run a focused security review of the codebase and close the one concrete gap it
surfaced (an unhardened production settings profile). Add `bandit` as a permanent,
CI-gated static-analysis tool, harden `settings/prod.py` so
`manage.py check --deploy` is clean, and record the findings as a durable audit
artifact.

This is a learning-grade project, so the value is as much in *documenting why the
existing controls are correct* as in adding new ones.

## Pre-review findings (recon)

Read-only recon already established the security baseline:

| Area | State | Evidence |
|---|---|---|
| Secrets hygiene | ✅ Clean | `.env` + `.env.*` gitignored and untracked; no hardcoded `sk_`/`whsec_` literals in `apps/`/`settings/`; `detect-private-key` pre-commit hook present |
| CSRF coverage | ✅ Correct | Standard Django CSRF middleware; the only `csrf_exempt` is `apps/payments/views.py::stripe_webhook` |
| Stripe webhook | ✅ Secure | `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)` verifies signature before processing; idempotent via `StripeEvent.get_or_create`; `select_for_update` row lock |
| **prod.py hardening** | ❌ **Gap** | `settings/prod.py` sets only `DEBUG=False` + email; no `SECURE_*` / secure-cookie / HSTS settings → `check --deploy` will warn |
| bandit | ⬜ Not run | Not installed; static-analysis findings unknown until first run |

**Conclusion:** the app logic and secrets handling are sound. The review's
deliverable is therefore *config + CI + docs + tests*, not application-logic fixes.

## Scope

**In scope**
1. Add `bandit` as a dev dependency + `[tool.bandit]` config; triage to clean; gate it in CI.
2. Harden `settings/prod.py` to a clean `check --deploy`.
3. Write the audit report to `docs/security-review.md`.
4. Regression test asserting the prod hardening flags (`tests/test_security_settings.py`).

**Out of scope (YAGNI)**
- A root `SECURITY.md` vulnerability-reporting policy (no public disclosure process for a learning project).
- Dependency CVE scanning (`pip-audit`/`safety`) — not in the backlog item; can be a later NFR.
- Any change to application logic (none needed — see findings).
- Real deployment wiring (TLS certs, actual proxy config) — post-M5.

## Design

### 1. bandit — dev dependency, config, CI gate

**Dependency** — add to `pyproject.toml` `[dependency-groups] dev`:
```
"bandit (>=1.8,<2.0)"
```

**Config** — `[tool.bandit]` in `pyproject.toml`:
```toml
[tool.bandit]
exclude_dirs = ["migrations", "tests", "media", "static", "locale", "htmlcov"]
```
Scan target is the first-party source only: `apps` and `settings`. Root `tests/`
is excluded (asserts → B101 noise; tests are not shipped code). Migrations are
auto-generated.

**Run command** (documented, used locally and in CI):
```
poetry run bandit -c pyproject.toml -r apps settings
```

**Triage policy** — drive to a clean run. Any finding that is a genuine
false-positive or an accepted risk gets an inline `# nosec BXXX` **with a
justification comment on the same construct** (never a blanket file-level skip).
Expected first-run findings are low/none, since the app avoids the usual bandit
triggers (no `subprocess`, `eval`, `pickle`, `random` for security, or
`hardcoded_password`); the Stripe webhook is signature-verified. Actual findings
are enumerated during implementation and recorded in the audit report.

**CI gate** — new step in the existing `quality` job in `.github/workflows/ci.yml`,
placed after the `Mypy` step, mirroring the ruff/mypy pattern:
```yaml
      - name: Bandit (security lint)
        run: poetry run bandit -c pyproject.toml -r apps settings
```
A non-zero bandit exit (any unsuppressed finding at its default severity/confidence
threshold) now fails CI like a lint error.

### 2. prod.py hardening

Append a security block to `settings/prod.py` (which already does
`from settings.base import *` and `DEBUG = False`):

```python
# --- Security hardening (US-42). Active only under settings.prod. ---
# HTTPS enforcement. Behind a TLS-terminating proxy (Heroku/Render/nginx),
# Django sees plain HTTP, so trust the proxy's X-Forwarded-Proto header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# Cookies only over HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — 1 year, include subdomains, allow preload-list submission.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Defense-in-depth headers (explicit even where Django already defaults).
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```

**Target:** `poetry run python manage.py check --deploy --settings=settings.prod`
reports **0 warnings**. (`SECRET_KEY` comes from env and is assumed strong in a
real deploy; the dev/CI dummy key is irrelevant to the prod profile check.)

These settings live in `prod.py` only — `dev.py` and the test profile
(`settings.dev`) are untouched, so local HTTP development and the test suite are
unaffected.

### 3. Audit report — `docs/security-review.md`

A standalone, durable artifact (chosen over root `SECURITY.md`, which conventionally
holds a reporting *policy*). Contents:
- Scope, date, tools and versions used.
- Findings table: bandit results + triage, CSRF coverage, secrets audit,
  `check --deploy` **before → after**.
- Justified exemptions, with reasoning — notably the signature-verified Stripe
  webhook `csrf_exempt`, and any `# nosec` annotations.

This is filled in with the *actual* tool output during implementation (the
`check --deploy` before/after and the bandit summary), so it reflects real results,
not predictions.

### 4. Regression test — `tests/test_security_settings.py`

A DB-free guard so the hardening can't silently regress. It imports the production
settings module and asserts each flag:

```python
import importlib

def test_prod_settings_are_hardened():
    prod = importlib.import_module("settings.prod")
    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS >= 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
```

Importing `settings.prod` re-executes the module (reading env via `environ` with
defaults); it does not reconfigure Django, so it is safe under the `settings.dev`
test profile. If the import proves to have a side effect under pytest, the fallback
is to read the values via `ast`/file parse — to be confirmed at implementation.

bandit itself is **not** wrapped in a pytest test; CI enforces it directly.

## Roles (per project workflow)

- **Claude prepares:** `pyproject.toml` (bandit dep + `[tool.bandit]`), the CI step,
  `settings/prod.py` hardening, `docs/security-review.md`, and the test
  (`tests/test_security_settings.py`). This mirrors US-40, where settings/CI/config
  were Claude-authored; no application logic changes here.
- **User runs:** `poetry add --group dev bandit` (or `poetry lock` + `install`),
  `bandit`, `check --deploy`, the full test suite, and all `git`/`gh` commands.

## Verification

1. `poetry add --group dev bandit` → lockfile updated, installs.
2. `poetry run bandit -c pyproject.toml -r apps settings` → clean (0 issues, or only justified `# nosec`).
3. `poetry run python manage.py check --deploy --settings=settings.prod` → 0 warnings.
4. `poetry run pytest` → full suite green incl. `tests/test_security_settings.py`; coverage ≥ 80% holds.
5. `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .` → green.
6. `docs/security-review.md` reflects the *actual* before/after and bandit output.

## Risks / notes

- **`check --deploy` residual warnings:** if any warning beyond the cookie/HSTS/SSL
  set appears (e.g., `SECRET_KEY` length under the CI dummy), it is triaged in the
  report; the prod target assumes a real strong env `SECRET_KEY`.
- **bandit version drift:** pin a minor range (`>=1.8,<2.0`) so a new rule release
  can't surprise-fail CI on an unrelated push.
- **prod-only blast radius:** all hardening is confined to `settings/prod.py`; dev
  and test profiles are unchanged, so there is no risk to local workflow or the suite.
