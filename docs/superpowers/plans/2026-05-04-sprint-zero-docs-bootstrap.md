# Sprint Zero — Docs & Repo Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize the approved design (`docs/superpowers/specs/2026-05-04-requirements-rework-design.md`) into 5 supplementary docs in `.Claude/`, a PR template, a baseline README, a `.gitignore`, and the first GitHub remote — *zero application code yet*.

**Architecture:** Pure documentation + repo bootstrapping milestone (sprint zero). Each task creates exactly one file and produces exactly one commit, so the git history reads like a literal table of contents. After this plan completes, the repo is in `M0 done / M1 ready` state — next step is `US-01` (Django bootstrap).

**Tech Stack:** Markdown, `git`, `gh` CLI. No Python/Django code yet.

**Source of truth for content:** Each task points to the spec section that defines what the file must say. The plan tells you *which file*, *what structure*, and *what to commit* — the spec tells you *the words*.

**Note on TDD:** Standard TDD doesn't apply to doc-only changes. The "verification" step for each task is a manual readback of the file (markdown renders cleanly, all sections present, no broken cross-refs).

---

## File Structure

After this plan, the repo layout will be:

```
cinema-booking-system/
├── .Claude/
│   ├── KinoMania_wymagania_funkcjonalne.md     (UPDATED v2.0 → v3.0)
│   ├── workflow_scrum_agile.md                 (NEW)
│   ├── backlog.md                              (NEW)
│   ├── tooling_stack.md                        (NEW)
│   └── commit_convention.md                    (NEW)
├── .github/
│   └── pull_request_template.md                (NEW)
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-05-04-requirements-rework-design.md  (already saved, will be committed)
│       └── plans/
│           └── 2026-05-04-sprint-zero-docs-bootstrap.md  (THIS FILE — committed)
├── .gitignore                                  (NEW)
├── README.md                                   (NEW — placeholder)
├── pyproject.toml                              (UNCHANGED — touched only in M1)
├── poetry.lock                                 (UNCHANGED)
└── .idea/                                      (gitignored)
```

## Pre-flight checks

- [ ] Verify current dir is `C:\Users\barte\PycharmProjects\cinema-booking-system`
- [ ] Verify the design file exists at `docs/superpowers/specs/2026-05-04-requirements-rework-design.md`
- [ ] Verify NOT a git repo yet (`git status` → "not a git repository")
- [ ] User has created an empty GitHub repo, has the `<remote-url>` ready (HTTPS or SSH form), and is authenticated (`gh auth status` → green). If not, pause and ask user before Task 9.

---

## Task 1: Initialize git repository and `.gitignore`

**Files:**
- Create: `.gitignore`

**Why first:** Every later task ends in a commit. Git must exist before any commit. We do **not** make a commit in this task — `.gitignore` lands as part of Task 9 (the bootstrap commit), so the very first commit can include both `.gitignore` and `README.md` together.

- [ ] **Step 1.1: Run `git init`**

```bash
git init -b main
```

Expected output:
```
Initialized empty Git repository in <path>/.git/
```

- [ ] **Step 1.2: Verify the default branch is `main`**

```bash
git symbolic-ref HEAD
```

Expected: `refs/heads/main`. If it says `master`, run:

```bash
git branch -m master main
```

- [ ] **Step 1.3: Create `.gitignore`**

Write file `.gitignore` with the following content (exact, no other entries):

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.installed.cfg
*.egg

# Virtualenv
.venv/
venv/
env/
ENV/

# Poetry
# (poetry.lock IS committed; only the cache is ignored)
.poetry-cache/

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/
staticfiles/
locale/*/LC_MESSAGES/*.mo

# Environment
.env
.env.*
!.env.example

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
desktop.ini

# Coverage / Test
htmlcov/
.coverage
.coverage.*
.cache
.pytest_cache/
.mypy_cache/
.ruff_cache/
coverage.xml
*.cover

# Docker
docker-compose.override.yml
```

- [ ] **Step 1.4: Verify file content**

```bash
cat .gitignore | head -10
```

Expected: starts with `# Python` block. No commit yet — proceed to Task 2.

---

## Task 2: Commit the design spec (T0.1)

**Files:**
- Already exists: `docs/superpowers/specs/2026-05-04-requirements-rework-design.md`
- Already exists: `docs/superpowers/plans/2026-05-04-sprint-zero-docs-bootstrap.md` (this plan)

**Why now:** With git initialized but `.gitignore` not yet committed, we want the spec + plan to be the *first* logical change committed. We hold the bootstrap commit (`.gitignore` + `README.md` + remote push) for Task 9 so we can include the GitHub remote setup in one atomic chore commit.

- [ ] **Step 2.1: Stage spec and plan files**

```bash
git add docs/superpowers/specs/2026-05-04-requirements-rework-design.md docs/superpowers/plans/2026-05-04-sprint-zero-docs-bootstrap.md
```

- [ ] **Step 2.2: Verify staged files**

```bash
git status
```

Expected: 2 new files staged under `docs/superpowers/`. Nothing else.

- [ ] **Step 2.3: Propose commit (do NOT execute without user approval)**

Show the user:

```bash
git commit -m "$(cat <<'EOF'
docs(infra): add brainstorm design and sprint zero plan

Captures the approved v3 requirements rework design (DRF + Stripe sandbox
+ SCRUM/AGILE workflow) and the sprint zero plan that materializes the
five supplementary docs into .Claude/.

Refs: T0.1
EOF
)"
```

Wait for "ok" / "merge" before executing. After commit, run `git log --oneline` and verify exactly one commit exists.

---

## Task 3: Update `KinoMania_wymagania_funkcjonalne.md` to v3.0 (T0.2)

**Files:**
- Modify: `.Claude/KinoMania_wymagania_funkcjonalne.md`

**What to change** — the spec section 2.2 lists every change. Concretely:

1. Bump header `**Wersja:** 2.0` → `**Wersja:** 3.0`. Keep `**Data:** 2026-05-04`.
2. Sekcja 1.2 — replace entire bullet list with the expanded one from spec §2.2 ("Sekcja 1.2 — założenia technologiczne").
3. Sekcja 3.8 (Booking) — extend the field table with: `expires_at`, `stripe_session_id`, `stripe_payment_intent_id`, `refund_id`, `refunded_at`. Update default status note: `default = PENDING` (was `CONFIRMED`).
4. Sekcja 3 — add new subsection `3.9 StripeEvent` with fields: `event_id` (CharField unique), `event_type`, `received_at`, `processed_at`, `payload` JSONField.
5. Sekcja 4 — append five new FRs verbatim from spec §2.2:
   - **FR-16** REST API auth
   - **FR-17** Public read-only API
   - **FR-18** Booking API
   - **FR-19** Admin/staff write API
   - **FR-20** OpenAPI/Swagger docs
   - **FR-21** Stripe Checkout integration
   - **FR-22** Stripe webhooks
   - **FR-23** Auto-expiration PENDING (`expire_pending_bookings`)
   - **FR-24** Refund flow on cancel
6. **FR-07 (Rezerwacja)** — replace the success path: instead of `Booking ze statusem CONFIRMED, redirect /bookings/<pk>/`, write the new flow: `Booking PENDING → Stripe Checkout redirect → webhook flips to CONFIRMED`.
7. **FR-13 (seed_db)** — add bullet: "5% generowanych bookingów ma status `PENDING` z `expires_at` w przeszłości i przyszłości (do testowania `expire_pending_bookings`)".
8. **FR-14 (testy)** — replace the section header note "django.test.TestCase" with "pytest-django + factory_boy". Add 4 new test groups verbatim from spec §2.2 (Stripe webhook signature, idempotency, expire command, refund flow).
9. Sekcja 5.1 — update `available_seats_count()` description: "liczy CONFIRMED + PENDING (z `expires_at > now()`) jako zajęte".
10. Sekcja 7 (niefunkcjonalne) — add 3 rows: throttling DRF (anon 100/h, user 1000/h, auth 20/h); webhook CSRF-exempt with signature verification; sekrety Stripe w `.env`.
11. Sekcja 8 (struktura projektu) — add to the tree: `cinema/api/`, `accounts/api/`, `payments/` (new app with stripe service + webhook + StripeEvent model), `docker-compose.yml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`.
12. Sekcja 9 (plan implementacji) — replace the 15-step list with a *milestone-based pointer* to `backlog.md`:
    > Ten dokument opisuje wymagania funkcjonalne. Plan implementacji (User Stories, kolejność, milestone) znajduje się w `backlog.md`. Workflow procesu — w `workflow_scrum_agile.md`.
13. Sekcja 10 (DoD) — add bullets:
    - Stripe Checkout flow działa end-to-end na sandbox keys
    - Webhook idempotency potwierdzona testem
    - `/api/v1/docs/` zwraca poprawną Swagger UI
    - `/api/v1/schema/` zwraca poprawny OpenAPI 3.1
    - JWT access/refresh działa, throttling skonfigurowany

- [ ] **Step 3.1: Read current file in full**

```
Read .Claude/KinoMania_wymagania_funkcjonalne.md
```

(Read tool — needed before any Edit per CC rules.)

- [ ] **Step 3.2: Apply edits one section at a time**

Use Edit tool for each of the 13 changes above. Do not Write the whole file (we'd lose history of intermediate state and risk reformatting). One Edit per section.

- [ ] **Step 3.3: Verify by re-reading**

After all edits, re-read the file and check:
- Header says v3.0
- 24 FR-XX entries are present (FR-01 through FR-24)
- `BookingStatus.PENDING` is no longer marked as unused
- `Stripe` mentioned at least 6 times
- `DRF` / `djangorestframework` mentioned

- [ ] **Step 3.4: Stage and propose commit**

```bash
git add .Claude/KinoMania_wymagania_funkcjonalne.md
git status   # only this file staged
```

```bash
git commit -m "$(cat <<'EOF'
docs(infra): bump requirements to v3.0 with DRF and Stripe

Adds FR-16..FR-24 covering parallel REST API (DRF + JWT + drf-spectacular)
and Stripe Checkout sandbox integration (FR-21..24 incl. webhook
idempotency, auto-expiration of PENDING bookings, refund flow on cancel).
Adjusts FR-07 booking flow to PENDING -> Checkout -> CONFIRMED.

Refs: T0.2
EOF
)"
```

Wait for user approval.

---

## Task 4: Create `.Claude/workflow_scrum_agile.md` (T0.3)

**Files:**
- Create: `.Claude/workflow_scrum_agile.md`

**Source of content:** spec §3 (whole section verbatim, with the markdown structure preserved).

- [ ] **Step 4.1: Write the file**

The file must contain these top-level sections (use `##` for each, copy content from the spec section noted in parentheses):

```markdown
# KinoMania — Workflow SCRUM/AGILE

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązany dokument:** `KinoMania_wymagania_funkcjonalne.md`, `backlog.md`

## 1. Model procesu  (z spec §3.1)
## 2. Role (z spec §3.2)
## 3. Obowiązki Claude (z spec §3.3)
## 4. Definition of Ready (DoR) (z spec §3.4)
## 5. Definition of Done (DoD) (z spec §3.5)
## 6. Ceremonie (z spec §3.6)
## 7. Milestone overview (z spec §3.7)
## 8. Eskalacja decyzji (z spec §3.8)
```

Each section copied **verbatim** from the spec. Drop the leading `### 3.X` numbering from the spec; renumber under `## N` as above.

- [ ] **Step 4.2: Verify**

```bash
wc -l .Claude/workflow_scrum_agile.md
```

Expected: ≥ 80 lines. Open and skim — every spec §3 subsection represented.

- [ ] **Step 4.3: Stage and propose commit**

```bash
git add .Claude/workflow_scrum_agile.md
```

```bash
git commit -m "$(cat <<'EOF'
docs(infra): document SCRUM/AGILE workflow for solo+AI

Captures the hybrid Kanban + monthly milestones model: roles, DoR/DoD,
lightweight ceremonies, milestone overview (M1..M5 -> v0.1.0..v1.0.0),
and decision-escalation rules between user (Product Owner) and Claude
(Developer + Tech Lead).

Refs: T0.3
EOF
)"
```

Wait for user approval.

---

## Task 5: Create `.Claude/backlog.md` (T0.4)

**Files:**
- Create: `.Claude/backlog.md`

**Source of content:** spec §4 (entire section).

- [ ] **Step 5.1: Write the file**

Top-level structure:

```markdown
# KinoMania — Product Backlog

**Wersja:** 1.0
**Data:** 2026-05-04
**Total:** 43 User Stories across 5 milestones

## 0. Format każdego elementu  (z spec §4.1)
## 1. M1 — Foundation (v0.1.0) — 9 US  (z spec §4.2, US-01 .. US-09 — pełne karty)
## 2. M2 — Catalog web (v0.2.0) — 8 US  (z spec §4.3 — tabela)
## 3. M3 — Booking web + Stripe (v0.3.0) — 11 US  (z spec §4.4 — tabela)
## 4. M4 — REST API (v0.4.0) — 8 US  (z spec §4.5 — tabela)
## 5. M5 — Polish (v1.0.0) — 7 US  (z spec §4.6 — tabela)
## 6. Konwencja branchy  (z spec §4.8)
## 7. Status board (live)
```

The "Status board (live)" section is **new** (not in the spec) — it's the working surface that Claude updates as US move through the kanban. Structure:

```markdown
## 7. Status board (live)

| Status | US |
|---|---|
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | _none_ |
| **Backlog** | US-01..US-43 |
| **Done** | _none_ |

> Claude aktualizuje tę tabelę przy każdej zmianie statusu US.
```

For M1 US-01..US-09 — copy the **full Story / AC / DoR / Tests-first card** from spec §4.2 verbatim. For M2..M5 — only the summary table (we'll expand into full cards just-in-time at milestone planning, per workflow §3.6 "Backlog refinement").

- [ ] **Step 5.2: Verify**

```bash
grep -c "^### US-" .Claude/backlog.md
```

Expected: at least 9 (full cards for M1). The other 34 US live in tables, not as `###` headings.

- [ ] **Step 5.3: Stage and propose commit**

```bash
git add .Claude/backlog.md
```

```bash
git commit -m "$(cat <<'EOF'
docs(infra): add product backlog with 43 user stories

M1 (US-01..09) defined in full with Story / AC (Given-When-Then) /
DoR / tests-first lists. M2..M5 (US-10..43) listed as summary tables —
to be expanded into full cards at milestone planning. Includes a live
status board updated by Claude as US progress through the kanban.

Refs: T0.4
EOF
)"
```

Wait for user approval.

---

## Task 6: Create `.Claude/tooling_stack.md` (T0.5)

**Files:**
- Create: `.Claude/tooling_stack.md`

**Source of content:** spec §5 verbatim — already mostly code blocks, no rewriting needed.

- [ ] **Step 6.1: Write the file**

Structure:

```markdown
# KinoMania — Tooling Stack

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązany dokument:** `KinoMania_wymagania_funkcjonalne.md`

## 1. Zależności (Poetry)  (spec §5.1)
## 2. Ruff (pyproject.toml)  (spec §5.2)
## 3. Mypy (pyproject.toml)  (spec §5.3)
## 4. Pytest (pyproject.toml)  (spec §5.4)
## 5. Coverage (pyproject.toml)  (spec §5.5)
## 6. Pre-commit (.pre-commit-config.yaml)  (spec §5.6)
## 7. GitHub Actions CI (.github/workflows/ci.yml)  (spec §5.7)
## 8. Docker Compose (docker-compose.yml)  (spec §5.8)
## 9. .env.example  (spec §5.9)
## 10. Factory Boy — konwencja  (spec §5.10)
## 11. Mockowanie Stripe w testach  (spec §5.11)
## 12. Polecenia developerskie (do README)  (spec §5.12)
```

All code blocks copied verbatim from the spec — these are the canonical configs M1 will use.

- [ ] **Step 6.2: Verify**

```bash
grep -c '^```' .Claude/tooling_stack.md
```

Expected: ≥ 16 (8 code blocks × 2 fences = 16; we have 9 toml/yaml/ini/bash blocks ⇒ 18). If less than 14, you're missing blocks.

- [ ] **Step 6.3: Stage and propose commit**

```bash
git add .Claude/tooling_stack.md
```

```bash
git commit -m "$(cat <<'EOF'
docs(infra): document tooling stack and configurations

Canonical configs for ruff, mypy, pytest, coverage (80%), pre-commit,
GitHub Actions CI, docker-compose (PG 16), .env.example, factory_boy
naming, Stripe mocking pattern, and developer command cheat sheet.
US-01..US-05 (M1) will paste these into pyproject.toml and friends.

Refs: T0.5
EOF
)"
```

Wait for user approval.

---

## Task 7: Create `.Claude/commit_convention.md` (T0.6)

**Files:**
- Create: `.Claude/commit_convention.md`

**Source of content:** spec §6 verbatim.

- [ ] **Step 7.1: Write the file**

Structure:

```markdown
# KinoMania — Commit & PR Convention

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązany dokument:** `workflow_scrum_agile.md`

## 1. Format commit message  (spec §6.1)
## 2. Allowed type  (spec §6.2)
## 3. Konwencja scope  (spec §6.3)
## 4. Przykłady  (spec §6.4)
## 5. Reguła "jeden commit = jedna spójna zmiana"  (spec §6.5)
## 6. Co Claude robi automatycznie przed commitem  (spec §6.6)
## 7. PR template  (spec §6.7)
## 8. PR title  (spec §6.8)
## 9. Release flow per milestone  (spec §6.9)
## 10. Operacje wymagające ręcznej akceptacji  (spec §6.10)
```

All examples copied verbatim — these will be the canonical reference.

- [ ] **Step 7.2: Verify**

```bash
grep -E "^(feat|fix|chore|docs|test|ci|refactor|style|perf|build|revert)\b" .Claude/commit_convention.md | wc -l
```

Expected: ≥ 6 (the example commit messages from spec §6.4).

- [ ] **Step 7.3: Stage and propose commit**

```bash
git add .Claude/commit_convention.md
```

```bash
git commit -m "$(cat <<'EOF'
docs(infra): document commit and PR conventions

Conventional Commits with FR-scoped commits (e.g. feat(FR-07): ...),
allowed types, scope rules, branch naming (feat/FR-XX-slug), PR
template, squash-merge title format, milestone release flow, and the
list of operations requiring manual approval (no force-push, no merge
to main without PR, no edits to existing migrations).

Refs: T0.6
EOF
)"
```

Wait for user approval.

---

## Task 8: Create `.github/pull_request_template.md` (T0.7)

**Files:**
- Create: `.github/pull_request_template.md`

**Source of content:** spec §6.7 verbatim.

- [ ] **Step 8.1: Create the directory and file**

```bash
mkdir -p .github
```

Then write `.github/pull_request_template.md`:

```markdown
## Summary
<1–3 bullety: co i dlaczego>

## Linked
- FR: FR-XX
- US: US-XX

## Definition of Done checklist
- [ ] Acceptance Criteria spełnione
- [ ] Testy napisane i przechodzące (`pytest`)
- [ ] Coverage ≥ 80%
- [ ] `ruff check`, `ruff format --check`, `mypy` — czyste
- [ ] Migracje OK na czystej bazie
- [ ] i18n: `gettext_lazy` na nowych stringach, `makemessages` uruchomione
- [ ] OpenAPI schema aktualny (jeśli dotyczy API)
- [ ] README zaktualizowane (jeśli setup się zmienił)

## Test plan
- [ ] <ręczny test 1>
- [ ] <ręczny test 2>

## Screenshots / API examples
<dla zmian UI lub API>

## Notes
<otwarte pytania, follow-upy, znane ograniczenia>
```

- [ ] **Step 8.2: Verify**

```bash
ls .github/pull_request_template.md
```

Expected: file exists. Open and confirm it matches the template above.

- [ ] **Step 8.3: Stage and propose commit**

```bash
git add .github/pull_request_template.md
```

```bash
git commit -m "$(cat <<'EOF'
chore(ci): add pull request template

GitHub auto-loads .github/pull_request_template.md when opening PRs via
gh CLI or web UI. Sections match the DoD from workflow_scrum_agile.md
so each PR self-checks against the milestone gates.

Refs: T0.7
EOF
)"
```

Wait for user approval.

---

## Task 9: Add baseline `README.md` and finalize bootstrap commit (T0.8 part A)

**Files:**
- Create: `README.md`

**What goes in:** A *placeholder* README that will be expanded at US-41 (M5 polish). It needs enough to make the GitHub repo not look empty and to point future readers at the spec.

- [ ] **Step 9.1: Write `README.md`**

```markdown
# KinoMania — Cinema Booking System

> **Status:** Sprint zero (docs bootstrap) — application code arrives in M1.

## What is this

KinoMania is a learning-grade Django + DRF cinema booking system with Stripe sandbox payments. Built end-to-end in milestones M1..M5 by a solo developer (bartek) with Claude (Opus 4.7) as Tech Lead / Developer assistant.

**Tech:** Python 3.13 · Django 6 · Django REST Framework · PostgreSQL 16 (docker-compose) · Stripe Checkout (sandbox) · Bootstrap 5 · pytest + factory_boy · ruff + mypy · GitHub Actions CI

## Documentation

| Doc | Purpose |
|---|---|
| [`.Claude/KinoMania_wymagania_funkcjonalne.md`](.Claude/KinoMania_wymagania_funkcjonalne.md) | Functional requirements (PL) |
| [`.Claude/workflow_scrum_agile.md`](.Claude/workflow_scrum_agile.md) | SCRUM/AGILE workflow definition |
| [`.Claude/backlog.md`](.Claude/backlog.md) | Product backlog (43 User Stories, M1..M5) |
| [`.Claude/tooling_stack.md`](.Claude/tooling_stack.md) | Tooling configurations (ruff/mypy/pytest/CI) |
| [`.Claude/commit_convention.md`](.Claude/commit_convention.md) | Commit + PR + branch conventions |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | Design specifications |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | Implementation plans per milestone |

## Setup

> Application setup will be added in M1 (US-01). For now, this repo holds documentation only.

## Milestones

- [ ] **M1 — Foundation** (`v0.1.0`) — Django bootstrap, custom User, Docker, CI
- [ ] **M2 — Catalog web** (`v0.2.0`) — Movies, screenings, search, admin
- [ ] **M3 — Booking + Stripe** (`v0.3.0`) — Reservations, Stripe Checkout, refunds
- [ ] **M4 — REST API** (`v0.4.0`) — Full DRF mirror with JWT + OpenAPI
- [ ] **M5 — Polish** (`v1.0.0`) — i18n PL/EN, error pages, performance, README rewrite

## License

TBD (private learning project).
```

- [ ] **Step 9.2: Verify**

```bash
git status
```

Expected: untracked files include `.gitignore` (from Task 1), `README.md`. Optionally also `pyproject.toml`, `poetry.lock`, `.idea/` — `.idea/` should be ignored by `.gitignore`.

```bash
git check-ignore .idea/workspace.xml
```

Expected output: `.idea/workspace.xml` (meaning: yes, ignored). If output is empty, the `.gitignore` did not register `.idea/` — re-check Task 1.

- [ ] **Step 9.3: Stage `.gitignore` + `README.md` + (optional) Poetry files**

```bash
git add .gitignore README.md pyproject.toml poetry.lock
git status
```

Expected: 4 files staged. No `.idea/`, no `__pycache__`, no `.env`.

- [ ] **Step 9.4: Propose bootstrap commit**

```bash
git commit -m "$(cat <<'EOF'
chore(infra): initialize repository with .gitignore and README placeholder

Adds .gitignore (Python/Django/Poetry/IDE/coverage/Docker), a README
landing page that points at the .Claude/ docs and lists the M1..M5
milestone roadmap, and stages the existing pyproject.toml + poetry.lock
that pre-existed locally. No application code yet — that starts at US-01.

Refs: T0.8
EOF
)"
```

Wait for user approval.

---

## Task 10: Add GitHub remote and push (T0.8 part B)

**Files:** none (only git config + push).

**Pre-requisite:** User has created an empty GitHub repo and provides the URL. The user MUST do this manually (Claude does not create GitHub repos for the user — see workflow §3.8 / spec §7.5).

- [ ] **Step 10.1: Ask user for remote URL**

If not already provided, ask:
> "Podaj URL nowego pustego repo GitHub (HTTPS lub SSH) — np. `git@github.com:bgozlinski/kinomania.git`."

- [ ] **Step 10.2: Add remote and verify**

```bash
git remote add origin <USER-PROVIDED-URL>
git remote -v
```

Expected: `origin <url> (fetch)` and `origin <url> (push)`.

- [ ] **Step 10.3: Verify auth**

```bash
gh auth status
```

Expected: logged in as `bgozlinski`. If not — user must run `gh auth login` (interactive — user types `! gh auth login` themselves; Claude does not run interactive logins).

- [ ] **Step 10.4: Push all commits**

```bash
git push -u origin main
```

Expected: 8 commits pushed (Task 2 through Task 9). Output ends with `Branch 'main' set up to track 'origin/main'.`

- [ ] **Step 10.5: Verify on GitHub**

```bash
gh repo view --web
```

(Opens browser.) Confirm:
- 8 commits visible in history
- README renders with the milestone checklist
- `.Claude/` folder visible with 5 docs
- `.github/pull_request_template.md` visible

**No commit needed for this task** — `git remote add` and `git push` don't create local commits.

---

## Task 11: Final verification & handoff to M1

- [ ] **Step 11.1: Verify commit log**

```bash
git log --oneline
```

Expected (newest first):
```
<sha> chore(infra): initialize repository with .gitignore and README placeholder
<sha> chore(ci): add pull request template
<sha> docs(infra): document commit and PR conventions
<sha> docs(infra): document tooling stack and configurations
<sha> docs(infra): add product backlog with 43 user stories
<sha> docs(infra): document SCRUM/AGILE workflow for solo+AI
<sha> docs(infra): bump requirements to v3.0 with DRF and Stripe
<sha> docs(infra): add brainstorm design and sprint zero plan
```

8 commits, no `pre-commit` running yet (it lands in US-04), all messages follow Conventional Commits.

- [ ] **Step 11.2: Verify file inventory**

```bash
find .Claude .github docs -type f | sort
```

Expected output (paths normalized):
```
.Claude/KinoMania_wymagania_funkcjonalne.md
.Claude/backlog.md
.Claude/commit_convention.md
.Claude/tooling_stack.md
.Claude/workflow_scrum_agile.md
.github/pull_request_template.md
docs/superpowers/plans/2026-05-04-sprint-zero-docs-bootstrap.md
docs/superpowers/specs/2026-05-04-requirements-rework-design.md
```

8 files. No more, no less.

- [ ] **Step 11.3: Update auto-memory**

Append to `MEMORY.md` index:

```markdown
- [Project bootstrap state](project_kinomania_bootstrap.md) — KinoMania repo structure, docs locations, current milestone state
```

Create `project_kinomania_bootstrap.md`:

```markdown
---
name: KinoMania project state
description: KinoMania repo structure, docs locations, milestone status — useful when re-entering project sessions
type: project
---

KinoMania (cinema booking system, learning project) — repo at `C:\Users\barte\PycharmProjects\cinema-booking-system`.

**Current state:** Sprint zero done (2026-05-04). Repo on GitHub, 8 docs commits, NO application code yet.

**Docs map:**
- `.Claude/KinoMania_wymagania_funkcjonalne.md` v3.0 — functional requirements (FR-01..FR-24)
- `.Claude/workflow_scrum_agile.md` — Hybrid Kanban + monthly milestones, WIP=1
- `.Claude/backlog.md` — 43 US across M1..M5; status board (live) is the working surface
- `.Claude/tooling_stack.md` — canonical configs for ruff/mypy/pytest/CI/docker-compose
- `.Claude/commit_convention.md` — Conventional Commits with FR scope (e.g. feat(FR-07): ...)
- `docs/superpowers/specs/2026-05-04-requirements-rework-design.md` — approved design

**Why:** Project uses non-default workflow (milestone-based instead of sprints, FR-scoped commits, parallel DRF + Django Templates for learning). Future sessions need this to avoid re-deriving.

**How to apply:** When user references "the spec", "backlog", "workflow", read the matching `.Claude/` file. When proposing commits, follow `.Claude/commit_convention.md`. Next milestone is M1 (US-01..US-09).
```

**No commit needed** — this lands in your auto-memory directory, not in the repo.

- [ ] **Step 11.4: Announce M1 readiness**

Print the following to the user:

```
Sprint zero complete. State: M0 done / M1 ready.
Next: US-01 (Django bootstrap with Poetry) — start a new conversation
or continue here, and I'll invoke writing-plans for the M1 plan.
```

---

## Self-Review (run inline before handing back to user)

**Spec coverage check** — for each Sprint Zero task in spec §7.2:

| Spec | Plan task |
|---|---|
| T0.1 — Save design + commit | Task 2 ✅ |
| T0.2 — Update requirements to v3.0 | Task 3 ✅ |
| T0.3 — workflow_scrum_agile.md | Task 4 ✅ |
| T0.4 — backlog.md | Task 5 ✅ |
| T0.5 — tooling_stack.md | Task 6 ✅ |
| T0.6 — commit_convention.md | Task 7 ✅ |
| T0.7 — pull_request_template.md | Task 8 ✅ |
| T0.8 — git init + .gitignore + README + push | Tasks 1, 9, 10 ✅ |

All T0.x covered. Plus Task 11 (final verification + memory update) as a deliberate plan extension.

**Placeholder scan:** Plan contains no "TBD"/"TODO"/"implement later". The README placeholder is intentional (user-facing string in the README itself, not a plan defect).

**Type/path consistency:** Branch names use `chore/M1-<slug>` and `feat/FR-XX-<slug>` consistently with `commit_convention.md` §3. No conflicting paths.

**Order safety:** Task 1 (git init) happens before any commit. Task 10 (push) happens after all commits. `.gitignore` lands in the bootstrap commit (Task 9) so `.idea/` doesn't accidentally end up in earlier commits — but earlier commits only stage explicit paths under `.Claude/`, `docs/`, `.github/`, so this is belt-and-braces only.
