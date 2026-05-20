# M2 — Catalog web planning kickoff

**Milestone:** M2 — Catalog web (`v0.2.0`)
**US:** US-10..US-17 (8 user stories)
**Status:** Planning kickoff (drafted 2026-05-20 at M1 close)
**Predecessor:** M1 — Foundation (`v0.1.0`) ✅ complete

This document is a session-start brief for M2. Read it before opening M2 brainstorming/planning sessions to avoid re-deriving context.

---

## Goal

Ship `v0.2.0` — KinoMania has a browsable catalog. Users can:
- View the movie list (repertuar)
- Filter/search the list (by genre, year, search text)
- Open a movie detail page with embedded trailer
- View the screening schedule for a given day

Admin-side: cinema staff manage Movies, Screenings, Halls, Genres, Actors, Directors through Django admin.

**Out of M2 scope:** booking flow (M3), payments (M3-M4), user reviews (M5), DRF API (M4-M5).

---

## Recommended ordering (with dependency rationale)

| # | US | Why this position |
|---|---|---|
| 1 | **US-10** — Models (Genre, Actor, Director, Hall, Movie, Screening) + migrations | Hard blocker. Everything else depends on these models. Single biggest design decision in M2. |
| 2 | **US-15** — Cinema admin (Movie/Actor/Director/Genre/Hall admin classes) | Cheapest way to populate test data manually + immediate visual feedback that models work. Mostly mechanical. |
| 3 | **US-16** — `seed_db` extension (Genres, Halls, Movies, Screenings) | Programmatic test data for the views in US-11..US-14. Extends established US-08 pattern. |
| 4 | **US-11** — MovieList view (repertuar) | First user-facing M2 view. Sets the pattern for template + pagination + URL conventions. |
| 5 | **US-13** — MovieDetail view + embedded trailer | Parallel-able with US-12 (same model layer, different view). Brings in iframe/CSP design decisions. |
| 6 | **US-12** — Filtering + search on MovieList | Extends US-11. Pure-Django form approach vs. htmx is a design call (see Risks). |
| 7 | **US-14** — ScreeningList view (daily schedule) | Needs Screening model + ideally MovieDetail link target. Date/timezone handling is the meat. |
| 8 | **US-17** — Performance: `prefetch_related` on M2M | **Measure-first, fix-second.** Profile US-11/12/13/14 queries with django-debug-toolbar or `assertNumQueries`, fix N+1s. |

WIP=1 stays — one US in progress at a time.

---

## What needs brainstorming vs. what goes straight to plan

### Brainstorm first (separate sessions)

- **US-10** — Model design is the milestone foundation. Decisions:
  - Which fields on Movie (runtime, age rating, year, poster, trailer URL)?
  - M2M vs FK for genres/actors/directors?
  - `through` table for Actor→Movie role labels (e.g., main vs. supporting)?
  - Hall: just `name` + `seats_count`, or full `Seat` model with `(row, number)`? US-19 (booking) needs `Seat` but it can be deferred to M3.
  - Brainstorm carefully — refactoring models post-migration is painful.
- **US-12** — Filter UX:
  - Django `Form` rendering server-side, or htmx for live filtering?
  - Pagination (Django `Paginator` vs. cursor)?
  - Query parameter design (`?genre=drama&year=2024&q=...`).
  - 15-min brainstorming session sufficient.
- **US-13** — Embedded YouTube:
  - URL handling: full link vs. extract video ID? Validation rules?
  - `iframe sandbox` attributes?
  - Privacy implications (Referrer-Policy, `youtube-nocookie.com` vs. `youtube.com`)?
  - Quick design call.
- **US-14** — Date selection UX:
  - Date picker (HTML5 `<input type="date">` vs. JS lib)?
  - Timezone handling (Europe/Warsaw is set; what about screenings near midnight)?
  - Default to today, or last-viewed date in session?

### Plan directly (no brainstorming needed)

- **US-15** — Mechanical: register N models with `list_display`/`search_fields`/`list_filter`. Follow Django admin idioms; mirror `apps/accounts/admin.py` style.
- **US-16** — Extends US-08 pattern verbatim. Decide counts (e.g., 5 genres, 3 halls, 30 movies, 200 screenings) and Faker locales (`pl_PL` for names; English-ish movie titles). One spec + plan.
- **US-17** — Measure (django-debug-toolbar in dev settings, or `assertNumQueries` in tests), then add `prefetch_related`/`select_related` where needed. Plan is data-driven.

---

## Risk areas (worth flagging now)

1. **Model migration ordering** — Adding M2M / FK constraints in the right order so existing accounts data doesn't break. Always run migrations on a fresh DB AND on a seeded DB during testing.
2. **Photo/poster storage** — `MEDIA_URL` / `MEDIA_ROOT` not yet configured (see `settings/base.py:88` comment `# Static / Media (placeholder — wypełnimy w US-09 i FR-15)`). US-09 didn't touch media; US-10 or US-13 will need it. **Action: bundle media config into US-10 or split as US-10a/10b.**
3. **Search performance** — Polish text + Postgres `to_tsvector` vs. simple `icontains`. M2 ships `icontains`; full-text search is a follow-up (US-17b or M3 add).
4. **Repertuar nav link** — currently points to `/` (set in US-09). In US-11 we'll repoint to `/movies/` (or chosen path). Cheap refactor; test in `tests/cinema/test_base_template.py::test_navbar_repertuar_links_to_home` will need to update.
5. **Stale `placeholder` comments in settings** — `settings/base.py:88` comment about US-09 should be cleaned up post-M1; double-check whether `STATIC_URL` / `MEDIA_URL` were actually wired.
6. **Cinema template directory** — After US-09, `templates/cinema/home.html` is the only cinema template. US-11/13/14 will add `movie_list.html`, `movie_detail.html`, `screening_list.html`. Convention: all under `templates/cinema/`.

---

## Pre-flight checklist (read these before M2 brainstorming)

- `.Claude/KinoMania_wymagania_funkcjonalne.md` — full functional spec
  - **§FR-01** (repertuar)
  - **§FR-02** (filtering/search)
  - **§FR-03** (movie detail)
  - **§FR-04** (screenings)
  - **§FR-3.2..3.7** (model definitions)
  - **§FR-11** (admin scope)
- `.Claude/backlog.md` §2 (M2 table) — current short titles; flesh out US-10..US-17 cards as part of brainstorming each one
- `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md` — spec format template (mirror for US-10 spec)
- `apps/accounts/models.py` + `apps/accounts/admin.py` — established patterns for model + admin
- `apps/cinema/management/commands/seed_db.py` — extension template for US-16
- `tests/cinema/test_seed_db.py` — test pattern template for management-command tests

---

## Recommended next session kickoff prompt

> Start M2 — brainstorm US-10 (cinema models). Read `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-3.2..3.7 first, then walk me through model decisions one at a time (which fields per model, FK vs M2M choices, the Hall→Seat question, where MEDIA_URL/MEDIA_ROOT live).

That gives the next session a focused entry point. After US-10 spec/plan/merge, the M2 pattern repeats: spec → plan → TDD execution → PR.

---

## Branch + commit convention reminder

- **Branch naming:**
  - `feat/FR-XX-short-description` for feature work
  - `perf/FR-XX-...` for US-17 (performance)
  - `feat/M2-...` for milestone-scoped baseline work (rare in M2)
- **Commit scope:** `feat(FR-XX): ...`, `test(FR-XX): ...`, `refactor(FR-XX): ...`, `docs(FR-XX): ...`
- **Branch protection on `main`** — every US gets a PR with the structure used in US-08/US-09 PRs:
  - Summary
  - Closes
  - Spec & Plan
  - Test plan checkboxes

---

## M2 completion criteria

- All 8 US (US-10..US-17) merged to `main`
- Coverage stays ≥80% globally
- Manual smoke: anon user can browse movie list, open a movie detail, filter by genre/year/text, see today's screenings
- `v0.2.0` tag + GitHub release cut

After M2 → **M3 — Booking web + Stripe (`v0.3.0`)**, 11 US (US-18..US-28).
