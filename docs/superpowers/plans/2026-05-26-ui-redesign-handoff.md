# UI redesign — handoff integration — Implementation Plan

**Goal:** Integrate the `templates_new/` prototype handoff pack into the live templates.

**Spec:** `docs/superpowers/specs/2026-05-26-ui-redesign-handoff-design.md`

**Role split:** Claude did the integration + tests; **you run** git/gh and capture screenshots later (US-43). Branch: `feat/ui-redesign` (off `main`).

---

### Task 1: CSS + base wiring — DONE
- [x] `static/css/addons.css` in place (copied from the pack, 355 lines).
- [x] `base.html` links `addons.css` after `components.css`.

### Task 2: Template swaps — DONE
- [x] Drop-in pack versions: `cinema/screening_list.html`, `booking/my_bookings.html`, `booking/booking_detail.html`, `booking/booking_form.html`, `403.html`, `404.html`, `_partials/booking_badge.html`.
- [x] `500.html` — **custom standalone** (not the pack's base-extending version) with `.km-error`, links theme+addons directly.

### Task 3: View context — DONE
- [x] `ScreeningListView.get_context_data` → `available_dates` (today + 6 days) for the date strip.
- [x] `BookingDetailView.get_queryset` → `prefetch_related("screening__movie__genres")` for the ticket's genres line (keeps query budget).

### Task 4: i18n — DONE
- [x] `makemessages -l pl -l en --ignore=templates_new/*`.
- [x] Filled 14 EN entries (6 empty + 8 fuzzy); cleared fuzzy flags.
- [x] `compilemessages`; EN coverage gate green.

### Task 5: Tests — DONE
- [x] Updated `test_screening_pill_shows_hour_grouped_by_hall` for the price-on-pill redesign.
- [x] Full suite green: **561 passed**, 99% coverage. ruff/format/mypy clean.

---

### Task 6: Manual eyeball + ship (You)

- [ ] **Step 1:** Run the app and click through the restyled pages (EN + PL):
  ```bash
  poetry run python manage.py seed_db --flush --posters
  poetry run python manage.py runserver
  ```
  Check: screening date strip + price pills, my-bookings tabs/rows, booking ticket
  (confirmed → success circle), booking-form summary rail, and `/no-such-url/` (404).
- [ ] **Step 2:** Delete the now-integrated scratch pack: `rm -rf templates_new`.
- [ ] **Step 3:** Commit + PR:
  ```bash
  git add static/css/addons.css templates/ apps/cinema/views.py apps/booking/views.py \
          tests/cinema/test_screening_list.py locale/ docs/superpowers/
  git commit -m "style(ui): integrate prototype handoff — km-* components + restyled booking/screening/error pages"
  git push -u origin feat/ui-redesign
  gh pr create --base main --title "style(ui): prototype handoff integration" \
    --body "Restyles screening list, my-bookings, booking detail/form, error pages with addons.css + km-* components. 500 kept standalone. i18n recompiled. 561 passed."
  ```

### Task 7: After this merges
- [ ] Resume **US-43**: rebase the `docs/M5-demo-screenshots` branch on `main`, then capture the screenshots from the **new** UI, finish US-43, tag `v1.0.0`.

---

## Self-review
- **500 standalone** preserved (server-error test green). **403/404** pack versions OK.
- **Price-on-list** reversal of US-21 is intentional (pack design) and test-covered.
- **No dead context:** `available_dates` + genres prefetch both consumed by templates.
- **i18n gate** green; PL fallback behavior unchanged.
- **Unwired:** `_partials/booking_badge.html` shipped but not yet `{% include %}`d; `.movie-card__badge`/`.movie-hero__rating` unused (movie_list/detail not in pack).
