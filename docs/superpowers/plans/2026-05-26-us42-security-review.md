# US-42 — Security Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bandit` as a CI-gated security linter, harden `settings/prod.py` to a clean `manage.py check --deploy`, and record the audit in `docs/security-review.md`.

**Architecture:** No application-logic changes — the recon (see spec) confirmed secrets hygiene, CSRF coverage, and the signature-verified Stripe webhook are already correct. Work is confined to `pyproject.toml` (bandit dep + config), `.github/workflows/ci.yml` (gate), `settings/prod.py` (hardening, prod-only blast radius), one DB-free regression test, and the audit doc.

**Tech Stack:** Python 3.13 · Django 6 · Poetry · bandit · pytest · GitHub Actions.

**Role split (project convention):** Claude edits all files below. **You run** every `poetry`/`bandit`/`python manage.py`/`pytest`/`ruff`/`mypy`/`git` command (shown in fenced blocks). Branch is already `chore/M5-security-review`.

**Spec:** `docs/superpowers/specs/2026-05-26-us42-security-review-design.md`

---

### Task 1: Add bandit dependency + `[tool.bandit]` config

**Files:**
- Modify: `pyproject.toml` (`[dependency-groups] dev` list; new `[tool.bandit]` section)

- [ ] **Step 1: Add the dependency line (Claude)**

Add to the `dev = [ ... ]` list in `[dependency-groups]`, matching the existing PEP 508 format, after `"django-debug-toolbar (>=6.3.0,<7.0.0)"`:

```toml
    "django-debug-toolbar (>=6.3.0,<7.0.0)",
    "bandit (>=1.8,<2.0)"
```

(Add a trailing comma to the `django-debug-toolbar` line so the list stays valid.)

- [ ] **Step 2: Add the bandit config (Claude)**

Append a `[tool.bandit]` section to `pyproject.toml` (after `[tool.coverage.report]`):

```toml
[tool.bandit]
# First-party source is scanned via `-r apps settings`; these dirs are excluded
# as noise (test asserts → B101) or generated/non-source.
exclude_dirs = ["migrations", "tests", "media", "static", "locale", "htmlcov"]
```

- [ ] **Step 3: Sync the lockfile and install (you run)**

```bash
poetry lock
poetry install
```
Expected: lockfile updates with `bandit`; install succeeds.

- [ ] **Step 4: Confirm bandit is available (you run)**

```bash
poetry run bandit --version
```
Expected: prints a `1.8.x` version.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "chore(NFR): add bandit security linter + config (US-42)"
```

---

### Task 2: First bandit run + triage to clean

**Files:**
- Possibly modify: app/settings source (only if a finding needs a justified `# nosec`)

- [ ] **Step 1: Run bandit (you run)**

```bash
poetry run bandit -c pyproject.toml -r apps settings
```
Expected: a results table. Paste the full output back so Claude can triage. Likely outcome is **0 issues** (no `subprocess`/`eval`/`pickle`/`random`-for-security/`hardcoded_password`; the Stripe webhook is signature-verified).

- [ ] **Step 2: Triage (Claude)**

For each reported issue, decide: genuine fix, or accepted/false-positive. Accepted/false-positive gets an inline annotation on the offending line **with a reason**, e.g.:

```python
some_call(...)  # nosec B603 — fixed argv, no shell, inputs are trusted constants
```
Never a blanket file-level or config-level skip. Record the raw bandit summary verbatim for Task 4.

- [ ] **Step 3: Re-run to confirm clean (you run, only if Step 2 changed files)**

```bash
poetry run bandit -c pyproject.toml -r apps settings
```
Expected: `No issues identified.` (exit 0).

- [ ] **Step 4: Commit (only if Step 2 changed files)**

```bash
git add -A
git commit -m "chore(NFR): annotate justified bandit exemptions (US-42)"
```
If bandit was clean with no edits, skip this commit.

---

### Task 3: Wire bandit into CI

**Files:**
- Modify: `.github/workflows/ci.yml` (`quality` job, after the `Mypy` step)

- [ ] **Step 1: Add the CI step (Claude)**

In the `quality` job, immediately after the `Mypy` step, add:

```yaml
      - name: Bandit (security lint)
        run: poetry run bandit -c pyproject.toml -r apps settings
```

- [ ] **Step 2: Validate YAML locally (you run)**

```bash
poetry run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('CI YAML OK')"
```
Expected: `CI YAML OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(NFR): gate bandit in the quality job (US-42)"
```

---

### Task 4: Harden `settings/prod.py` (TDD)

**Files:**
- Create: `tests/test_security_settings.py`
- Modify: `settings/prod.py`

- [ ] **Step 1: Capture the BEFORE deploy-check (you run)**

```bash
poetry run python manage.py check --deploy --settings=settings.prod
```
Expected: several `W00x`/`W01x` security warnings (no HSTS, `SECURE_SSL_REDIRECT`, secure cookies). Paste the output back — it's the "before" column of the audit report.

- [ ] **Step 2: Write the failing test (Claude)**

Create `tests/test_security_settings.py`:

```python
"""US-42: regression guard for production security hardening (settings.prod)."""

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

- [ ] **Step 3: Run the test to verify it fails (you run)**

```bash
poetry run pytest tests/test_security_settings.py -v --no-cov
```
Expected: FAIL — `AttributeError: module 'settings.prod' has no attribute 'SECURE_SSL_REDIRECT'`.

> If instead it fails at *import* (e.g. `environ` raising on a missing required env var), report the error — the fallback is to assert via file parse rather than import (noted in the spec). Otherwise continue.

- [ ] **Step 4: Harden prod.py (Claude)**

Append to `settings/prod.py`:

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

- [ ] **Step 5: Run the test to verify it passes (you run)**

```bash
poetry run pytest tests/test_security_settings.py -v --no-cov
```
Expected: PASS.

- [ ] **Step 6: Capture the AFTER deploy-check (you run)**

```bash
poetry run python manage.py check --deploy --settings=settings.prod
```
Expected: `System check identified no issues (0 silenced).` — 0 warnings. Paste it back for the audit report's "after" column. If any warning remains, report it for triage before committing.

- [ ] **Step 7: Commit**

```bash
git add settings/prod.py tests/test_security_settings.py
git commit -m "feat(NFR): harden prod.py security settings + regression test (US-42)"
```

---

### Task 5: Write the audit report

**Files:**
- Create: `docs/security-review.md`

- [ ] **Step 1: Write the report (Claude)**

Create `docs/security-review.md` using the **actual** outputs gathered above. Template (Claude fills bracketed values from real tool output — no predictions):

```markdown
# Security Review — KinoMania (US-42)

**Date:** 2026-05-26 · **Branch:** `chore/M5-security-review` · **Scope:** full codebase

## Tools
- bandit `[version]` — `poetry run bandit -c pyproject.toml -r apps settings`
- Django deploy check — `python manage.py check --deploy --settings=settings.prod`
- Manual review — secrets handling, CSRF coverage, Stripe webhook

## Findings

| Area | Result | Notes |
|---|---|---|
| Secrets hygiene | PASS | `.env`/`.env.*` gitignored + untracked; no hardcoded `sk_`/`whsec_` in `apps/`/`settings/`; `detect-private-key` pre-commit hook |
| CSRF coverage | PASS | Standard Django CSRF middleware; sole `csrf_exempt` is the Stripe webhook (justified — see below) |
| Stripe webhook | PASS | `stripe.Webhook.construct_event(...)` signature verification; idempotent (`StripeEvent`); `select_for_update` lock |
| bandit static analysis | [PASS / N issues] | [summary of triage] |
| Deploy hardening | FIXED | `check --deploy`: [N] warnings → 0 (see before/after) |

## Deploy check: before → after
**Before:**
```
[paste BEFORE output from Task 4 Step 1]
```
**After:**
```
[paste AFTER output from Task 4 Step 6]
```

## Justified exemptions
- **`apps/payments/views.py::stripe_webhook` — `@csrf_exempt`:** Stripe posts server-to-server, so CSRF tokens don't apply; authenticity is instead enforced by HMAC signature verification (`construct_event` with `STRIPE_WEBHOOK_SECRET`). Removing the exemption would break legitimate webhooks without adding security.
- [any `# nosec` annotations from Task 2, with reasons]

## Out of scope (future NFR)
- Dependency CVE scanning (`pip-audit`/`safety`).
- Real deployment wiring (TLS certs, runtime proxy config).
- Public vulnerability-reporting policy (root `SECURITY.md`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/security-review.md
git commit -m "docs(M5): US-42 security review report"
```

---

### Task 6: Full verification

- [ ] **Step 1: Lint + type-check (you run)**

```bash
poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .
```
Expected: all green.

- [ ] **Step 2: Full test suite with coverage (you run)**

```bash
poetry run pytest --cov-fail-under=80
```
Expected: full suite green (incl. `tests/test_security_settings.py`); coverage ≥ 80%.

- [ ] **Step 3: Final bandit + deploy-check sanity (you run)**

```bash
poetry run bandit -c pyproject.toml -r apps settings
poetry run python manage.py check --deploy --settings=settings.prod
```
Expected: bandit clean; deploy check 0 warnings.

- [ ] **Step 4: Push + open PR (you run)**

```bash
git push -u origin chore/M5-security-review
gh pr create --base main --title "chore(NFR): security review — bandit CI gate + prod hardening (US-42)" --body "Closes US-42. See docs/security-review.md."
```

---

## Self-review

- **Spec coverage:** bandit dep+config (Task 1), triage (Task 2), CI gate (Task 3), prod hardening + `check --deploy` clean (Task 4), audit report (Task 5), regression test (Task 4 Step 2), full verification (Task 6) — every spec section maps to a task.
- **Placeholders:** the report template's bracketed values are intentionally filled from *real* tool output at execution; no logic/code placeholders remain.
- **Type/name consistency:** every asserted attribute in the Task 4 test matches a setting written in the same task's hardening block (`SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`).
