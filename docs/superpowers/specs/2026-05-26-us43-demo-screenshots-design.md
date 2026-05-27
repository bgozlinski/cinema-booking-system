# US-43 — Final demo data + screenshots for README

- **Milestone:** M5 — Security & i18n polish (`v1.0.0`) — **final story**
- **Type:** infra · **Size:** S · **Branch:** `docs/M5-demo-screenshots`
- **Backlog:** "Final demo data + screenshots do README"
- **Date:** 2026-05-26

## Goal

Make the seeded demo data presentable, capture a set of README screenshots from the
finished, translated UI, and wire them into the README. This is the **last** M5 story —
after it merges, M5 is complete and the project is tagged `v1.0.0`.

Per `m5_planning.md`, US-43 is docs/infra and skips full TDD. The one piece of real code
(the seed change) does get a test; everything else is verified by the rendered docs and a
green suite.

## Decisions (from scoping with the user)

| Decision | Choice |
|---|---|
| Demo data | **Curated dataset + posters** — replace faker buzzword titles with original fictional titles + synopses; generate poster art. |
| Posters | **Opt-in `--posters` flag** (off by default) — generated, not bundled. |
| Who captures screenshots | **User captures** (runs the app); Claude wires the README + writes the capture checklist. |
| UI language | **English** (widest audience; no dedicated switcher shot). |
| Poster licensing | **Generated original gradient art** — the repo ships no copyrighted poster images. |

## The problem with the current demo data

- Movie titles come from `fake.catch_phrase()` → corporate buzzword strings, not film names.
- `seed_db` sets **no posters**, so every movie card/detail/screening renders the 🎬
  placeholder. Both look poor in a portfolio README.

## Why `--posters` is opt-in (not always-on)

`tests/cinema/test_seed_db.py` calls `seed_db` ~30 times. Generating ~20 poster PNGs per
call by default would slow the suite and write image files into `MEDIA_ROOT`. With the flag
off by default, the existing tests are unchanged; the demo/capture flow passes `--posters`.

## Verified codebase facts

- `Movie.poster` is an `ImageField(upload_to="posters/", blank=True)`; templates
  (`movie_list`, `movie_detail`, `screening_list`) render `movie.poster.url` or a 🎬
  placeholder.
- Pillow `>=11.0,<12` is already a dependency; `ImageFont.load_default(size=...)` returns a
  sized FreeType font in Pillow 11 (verified 11.3.0).
- Existing seed tests assert: exactly 20 movies at default / N at `--movies=N`; non-empty
  title & description; `duration_minutes` ∈ [80, 180]; `release_date` within the last 730
  days; m2m counts (genres 1–3, actors 3–8, directors 1–2). The curated data must satisfy
  all of these.
- Seed users' default password is `test1234` (`SEED_DB_DEFAULT_PASSWORD`); 80% are active.
- README currently has **no** Screenshots section (US-41 deliberately omitted it) and lists
  M5 as the only unchecked milestone.

## Scope

**In scope**

- `apps/cinema/management/commands/seed_db.py`:
  - `CURATED_MOVIES` pool (≥ 20 original fictional title/duration/synopsis tuples).
  - `_seed_movies` uses the pool for the first N movies, faker for any overflow.
  - New `--posters` flag + `_attach_poster` (Pillow gradient + wrapped title + footer),
    saved via `ImageField.save`.
- `tests/cinema/test_seed_db.py`: two new tests — posters off by default, and `--posters`
  attaches valid PNGs (using a tmp `MEDIA_ROOT`).
- `docs/screenshots/README.md`: capture checklist (prep + exact filenames + per-shot guide).
- `README.md`: new **Screenshots** section (8 images, 2-per-row), `--posters` documented in
  the seed options, M5 milestone checked.

**Out of scope (YAGNI)**

- Taking the screenshots (the user captures them) and committing the image binaries.
- Bundling real movie posters or stock images.
- Any change to app views/templates/models.
- The `v1.0.0` tag + GitHub release (a separate manual step after merge).

## Roles (per project workflow)

- **Claude prepares:** the `seed_db.py` demo-data + `--posters` code, the two seed tests,
  `docs/screenshots/README.md`, and the README edits.
- **User runs:** `seed_db --flush --posters`, captures the 8 screenshots into
  `docs/screenshots/`, runs the verification commands, and all `git`/`gh`.

## The 8 screenshots

`home.png`, `movie-list.png`, `movie-detail.png`, `screening-list.png`, `booking.png`,
`my-bookings.png`, `admin.png`, `api-docs.png` — see `docs/screenshots/README.md` for the
per-shot capture guide. The README references these exact filenames, so the section renders
as soon as the files are added.

## Verification

1. `pytest tests/cinema/test_seed_db.py` — all green (existing + 2 new). ✅ (39 passed)
2. `seed_db --flush --posters` produces curated titles + posters; the catalog/detail pages
   show real-looking cards (user confirms while capturing).
3. `ruff`/`mypy` clean on the changed Python; full `pytest` stays green.
4. README renders: Screenshots table well-formed, images resolve once captured, M5 checked.

## Risks / notes

- **Broken images until captured:** the README references files that don't exist yet; it
  shows broken-image icons until the user drops them in. Expected — the capture step
  closes it.
- **`hash()` is per-process salted** → poster hue varies run-to-run; acceptable (we want
  variety, not reproducibility).
- **Poster generation cost:** ~20 gradients (600 line draws each) only when `--posters` is
  passed — negligible for a one-off demo seed, absent from the test suite.
- **M5 checkbox:** flipped to ✅ in this PR since US-43 is the completing story; the actual
  `v1.0.0` tag is a manual post-merge step.
