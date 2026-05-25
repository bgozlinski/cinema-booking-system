# M5 — Polish (`v1.0.0`) planning kickoff

**Milestone:** M5 — Security & i18n polish (`v1.0.0`) — **final milestone**
**US:** US-37..US-43 (7 user stories)
**Status:** Planning kickoff (drafted 2026-05-25 at M4 close)
**Predecessor:** M4 — REST API (`v0.4.0`) ✅ complete (US-01..US-36)

Session-start brief for M5. Read before opening M5 brainstorming/planning sessions. Mirrors
`m4_planning.md`.

---

## Goal

Ship `v1.0.0` — production-ready polish: PL/EN internationalization, custom error pages,
a performance/security pass, and the docs/demo material a 1.0 release needs.

**Out of M5 scope:** new features (the app is feature-complete after M4); real deployment
(post-1.0); translating API responses (DRF stays English per FR §652) or URLs
(`i18n_patterns` not used — FR-15).

---

## The 7 stories (backlog §5)

| US | Title | FR | Estym | Branch |
|----|-------|----|-------|--------|
| US-37 | i18n: makemessages/compilemessages, **language switcher** | FR-15 | L | `feat/FR-15-i18n-setup` |
| US-38 | Translations PL/EN — **all** user-facing strings | FR-15 | M | `feat/FR-15-translations` |
| US-39 | Custom 403/404/500 templates + flash polish | FR-12 | S | `feat/FR-12-error-pages` |
| US-40 | Performance audit (Debug Toolbar, query-count assertions) | NFR | S | `perf/M5-query-audit` |
| US-41 | README rewrite (setup, troubleshooting, architecture) | infra | M | `docs/M5-readme-rewrite` |
| US-42 | Security review (bandit, CSRF coverage, secrets audit) | NFR | S | `chore/M5-security-review` |
| US-43 | Final demo data + screenshots for README | infra | S | `docs/M5-demo-screenshots` |

---

## Recommended ordering (with rationale)

| # | US | Type | Why this position |
|---|----|------|-------------------|
| 1 | **US-37** — i18n infra + switcher | **mixed** | Foundation. Settings (LANGUAGE_CODE/LANGUAGES/LOCALE_PATHS/USE_I18N), `LocaleMiddleware` (after Session, before Common), `i18n/` URL, navbar language switcher (POST to `set_language`). One design point: switcher UX in the dark-theme navbar + persistence (cookie/session). Proves makemessages/compilemessages pipeline on a representative set of strings. |
| 2 | **US-38** — translate all strings | **plan-directly** | Mechanical but large surface: wrap every user-facing string (`verbose_name`/`help_text`/`choices`, forms, **all templates incl. the PR #18/#19 redesign**, view `messages`) in `gettext[_lazy]`; `makemessages -l en -l pl`; fill `pl` + `en` `.po`; `compilemessages`. Depends on US-37 infra. |
| 3 | **US-39** — error pages | **plan-directly** | Custom `403/404/500` templates extending `base.html` (dark theme) + flash polish. Independent; needs `DEBUG=False` handler testing. |
| 4 | **US-40** — perf audit | **plan-directly** | django-debug-toolbar (dev-only) + query-count assertions on the heavy list views/API. The `django_assert_max_num_queries` pattern already exists (M2/M3). |
| 5 | **US-42** — security review | **plan-directly** | `bandit` run + triage, CSRF coverage check, secrets audit (`.env` not committed, no hardcoded keys). Add `bandit` as a dev tool. |
| 6 | **US-41** — README rewrite | **plan-directly** | Docs-only; do **late** so it documents the final state (i18n, error pages, the full API). |
| 7 | **US-43** — demo data + screenshots | **plan-directly** | Docs/infra; **last** — screenshots need the finished, translated UI. |

WIP=1. Per-US: brainstorm (if flagged) → spec → plan → TDD → PR. **US-41/US-43 are docs-only**
(`docs/M5-*` branches) — no code/tests, so they skip TDD (verification = the rendered docs).

---

## What needs brainstorming vs plan-directly

- **US-37** (mixed): the language-switcher UX (form placement in the redesigned navbar,
  `select` + auto-submit vs button, `next` hidden field) and language persistence
  (LocaleMiddleware reads cookie/session/Accept-Language). Plus the US-37/US-38 boundary
  (below). Worth a short brainstorm.
- **US-38..43** (plan-directly): standard Django i18n / docs / tooling work.

## US-37 ↔ US-38 boundary (settle at US-37 kickoff)

Per the backlog split: **US-37 = the i18n *machinery*** (settings/middleware/URL/switcher +
the makemessages/compilemessages workflow working, marking a representative slice so the
switcher demonstrably flips a real string). **US-38 = exhaustive content** (mark *every*
remaining string across models/forms/templates/messages + complete `pl`+`en` translations +
compile). Confirm this split when scoping US-37 so strings don't get double-handled.

---

## Risks

1. **gettext on Windows.** `makemessages`/`compilemessages` need the GNU `gettext` binaries
   (`xgettext`, `msgfmt`) on PATH. The user is on Windows (Git Bash). **Mitigation:** install
   gettext (e.g. via the Django-recommended Windows build or `choco install gettext`) and
   verify `python manage.py makemessages` runs before US-37 implementation. Flag at US-37 start.
2. **i18n string-marking is invasive** — touches every app's models/forms/templates/views,
   including the dark-theme redesign templates (PR #18/#19) which currently hold hardcoded
   Polish. Large diff in US-38; keep US-37's marking to a demonstrable slice.
3. **Testing i18n** — use `translation.override("en")` / `activate()` + assert a translated
   string renders; avoid asserting raw locale formatting (dev pitfalls #4/#5 — TZ/decimal).
4. **`.mo` files in git** — decide whether compiled `.mo` are committed or gitignored +
   compiled in CI/deploy. Simplest for this project: commit `.mo` (no compile step in CI).
   Settle in US-37/38.
5. **Error-page testing needs `DEBUG=False`** — 404/500 handlers only render custom templates
   when `DEBUG=False`; tests use `@override_settings(DEBUG=False)` + a deliberately broken
   route / `client.raise_request_exception=False`.
6. **bandit findings noise** — triage; many are low-severity (e.g. `assert` in tests already
   ignored by ruff S101). Document accepted findings; don't chase false positives.
7. **Coverage ≥80% holds** — US-37/39/40 add small code; US-41/43 are docs (no coverage
   impact); US-42 may add a bandit config. Translations (US-38) add no Python logic.

---

## Pre-flight checklist (read before M5 brainstorming)

- **FR doc:** `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-15 (i18n — detailed),
  §FR-12 (error handling), §6 (UI/UX — navbar switcher), §7 (NFR — security/perf).
- **Backlog:** `.Claude/backlog.md` §5 (M5 table US-37..43).
- **Tooling:** `.Claude/tooling_stack.md` (django-debug-toolbar already listed in dev deps §1;
  add `bandit` for US-42; gettext commands in §12).
- **Memory:** `project_kinomania_bootstrap.md` (repo state post-M4), `feedback_role_division`
  (user writes app code + runs git; Claude writes tests), `feedback_us_branch_timing`
  (branch-first!), `feedback_shell_environment` (Git Bash heredocs),
  `feedback_pycharm_django_templates` (hard-wrap breaks `{% %}` — relevant for `{% trans %}`
  / `{% blocktrans %}` in US-37/38).
- **Templates to translate (US-38):** `templates/base.html`, `templates/cinema/*`,
  `templates/booking/*`, `templates/accounts/*` (+ `_auth_base.html`).

---

## M5 completion criteria

- ✅ All 7 US (US-37..43) merged to `main`.
- ✅ PL/EN switcher works; all user-facing strings translated; `compilemessages` clean.
- ✅ Custom 403/404/500 render under `DEBUG=False`.
- ✅ Perf assertions green; security review documented (bandit triaged, no committed secrets).
- ✅ README + demo screenshots reflect the finished app.
- ✅ Coverage ≥80%; `mypy`/`ruff` clean.
- ✅ `v1.0.0` tag + GitHub release.
- ✅ Memory update: `project_kinomania_bootstrap.md` reflects **project complete** (M1..M5).

---

## Branch + commit conventions (reminder)

- Branches per backlog §5: `feat/FR-15-i18n-setup` (US-37), `feat/FR-15-translations` (US-38),
  `feat/FR-12-error-pages`, `perf/M5-query-audit`, `chore/M5-security-review`,
  `docs/M5-readme-rewrite`, `docs/M5-demo-screenshots`.
- Commit: Conventional Commits with FR scope (`feat(FR-15): …`); docs-only US use `docs(M5): …`.
- **Branch-first** (per `feedback_us_branch_timing`): create the branch BEFORE writing any
  spec/plan/test files. This `m5_planning.md` folds into US-37's first commit (like
  `m4_planning.md` did for US-29).
- PR per US: Summary / Linked (Spec + Plan + Closes US-XX) / DoD / Test plan / Out of scope.

---

## Recommended next-session kickoff prompt

> Start US-37 — brainstorm i18n setup. Read `.Claude/m5_planning.md` then
> `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-15. **First: verify `gettext` is on PATH**
> (`python manage.py makemessages --help` / a dry run) — it's the #1 M5 risk on Windows. Then
> walk me through: settings + `LocaleMiddleware` placement, the navbar language switcher
> (`set_language` POST), and the US-37↔US-38 string-marking boundary.

After US-37 → US-38..43 follow the ordering above. After M5 → **project complete (`v1.0.0`)**.
