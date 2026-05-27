# US-43 — Final demo data + README screenshots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the seed produce presentable demo data (curated titles + opt-in generated posters), wire a Screenshots section into the README, and provide a capture checklist. Last M5 story → `v1.0.0`.

**Architecture:** One code change (`seed_db.py`) with a test; the rest is docs/infra. The `--posters` flag is opt-in so the ~30 existing seed tests stay fast and write no images. Posters are generated original art (no bundled copyrighted images). Screenshots are captured by the user into `docs/screenshots/` against the filenames the README already references.

**Tech Stack:** Python · Pillow 11 · Markdown.

**Role split:** Claude writes the seed code, the seed tests, the capture checklist, and the README edits. **You run** `seed_db --flush --posters`, capture the 8 screenshots, run verification, and all `git`/`gh`. Branch is already `docs/M5-demo-screenshots`.

**Spec:** `docs/superpowers/specs/2026-05-26-us43-demo-screenshots-design.md`

---

### Task 1: Curated demo data + `--posters` (Claude) — DONE

**Files:** Modify `apps/cinema/management/commands/seed_db.py`

- [x] Add `CURATED_MOVIES` (24 original fictional title/duration/synopsis tuples; durations within 80–180).
- [x] `_seed_movies(... with_posters=False)` — use `CURATED_MOVIES[i]` for the first N movies, faker for overflow; keep release-date/m2m logic.
- [x] Add `--posters` store-true argument; wire it through `handle()`.
- [x] `_attach_poster(movie)` — Pillow gradient (hue from title hash) + width-wrapped title + `KINOMANIA` footer → `movie.poster.save(slugify(title)+".png", ...)`; Pillow imported lazily inside the helper.

### Task 2: Seed tests (Claude) — DONE

**Files:** Modify `tests/cinema/test_seed_db.py`

- [x] `test_seed_db_no_posters_by_default` — plain seed leaves `movie.poster` empty (tmp `MEDIA_ROOT`).
- [x] `test_seed_db_posters_flag_attaches_png_images` — `--posters` attaches files ending `.png`, present in storage, with PNG magic bytes.
- [x] Verified: `pytest tests/cinema/test_seed_db.py` → **39 passed** (37 existing + 2 new), seed_db 96% covered.

### Task 3: Capture checklist (Claude) — DONE

**Files:** Create `docs/screenshots/README.md`

- [x] Prep steps (`seed_db --flush --posters`, createsuperuser, runserver, switch to EN, ~1440px, log in as `seed.user1@kinomania.local`/`test1234`) + per-shot table for the 8 files. Also makes the `docs/screenshots/` dir exist in git.

### Task 4: README wiring (Claude) — DONE

**Files:** Modify `README.md`

- [x] New **Screenshots** section after Features — 8 images in a 2-per-row table referencing `docs/screenshots/*.png`.
- [x] Document `--posters` in the seed options + a `seed_db --flush --posters` tip.
- [x] Flip the **M5** milestone checkbox to `[x]`.

---

### Task 5: Capture the screenshots (You)

- [ ] **Step 1:** Seed + run, EN UI:
  ```bash
  poetry run python manage.py seed_db --flush --posters
  poetry run python manage.py runserver
  ```
- [ ] **Step 2:** Capture the 8 PNGs per `docs/screenshots/README.md` into `docs/screenshots/` using the exact filenames. Confirm the README Screenshots section renders (no broken images).

### Task 6: Verify + PR (You)

- [ ] **Step 1:** Quality on the change:
  ```bash
  poetry run ruff check apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
  poetry run ruff format --check apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
  poetry run mypy apps/cinema/management/commands/seed_db.py
  poetry run pytest -q
  ```
  Expected: clean + full suite green.
- [ ] **Step 2:** Commit (suggested):
  ```bash
  git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py \
          docs/screenshots/ docs/superpowers/specs/2026-05-26-us43-demo-screenshots-design.md \
          docs/superpowers/plans/2026-05-26-us43-demo-screenshots.md README.md
  git commit -m "docs(M5): curated demo data + --posters + README screenshots (US-43)"
  # then, after capturing the images:
  git add docs/screenshots/*.png
  git commit -m "docs(M5): add README screenshots (US-43)"
  ```
- [ ] **Step 3:** Push + PR:
  ```bash
  git push -u origin docs/M5-demo-screenshots
  gh pr create --base main \
    --title "docs(M5): final demo data + README screenshots (US-43)" \
    --body "Closes US-43. Curated seed movies + opt-in --posters generated art, README Screenshots section + capture checklist. Completes M5 → v1.0.0."
  ```

### Task 7: Release (You) — after merge

- [ ] `git tag v1.0.0 && git push origin v1.0.0`
- [ ] `gh release create v1.0.0` — project complete (M1–M5).

---

## Self-review

- **Spec coverage:** curated data + `--posters` (Task 1), tests (Task 2), capture checklist (Task 3), README (Task 4), capture + verify + PR + release (Tasks 5–7). Every spec in-scope item maps to a task.
- **Test-safety:** posters opt-in → existing seed tests untouched; new tests use tmp `MEDIA_ROOT`. Verified 39 passed.
- **Licensing:** posters generated, not bundled; titles original fictional — repo stays license-clean.
- **Known transient:** README image links resolve only after Task 5 (user captures the PNGs).
