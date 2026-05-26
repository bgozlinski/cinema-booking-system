# Screenshot capture checklist (US-43)

The README's **Screenshots** section embeds the eight `.png` files listed below. They are
**not** auto-generated — capture them by hand from a running instance and drop them in this
directory using the exact filenames. Until then, the README shows broken-image icons.

## Prep (once)

1. **Seed presentable demo data with posters:**
   ```bash
   poetry run python manage.py seed_db --flush --posters
   ```
   `--posters` generates original gradient poster art (no copyrighted images). Curated
   movie titles/synopses come from `CURATED_MOVIES` in `seed_db.py`.
2. **Create an admin** (for the admin shot) if you don't have one:
   `poetry run python manage.py createsuperuser`.
3. **Run the server:** `poetry run python manage.py runserver`.
4. **Switch the UI to English** via the navbar language switcher (all screenshots are EN).
5. **Browser:** use a clean window at ~**1440 px** wide, normal zoom (100%). Hide the
   Django Debug Toolbar handle if it's showing (it's already disabled under tests, but the
   dev server shows it) — or capture the content area only.
6. For the **My bookings** / **Seat booking** shots, log in as a seeded user
   (`seed.user1@kinomania.local` / `test1234`). If that user has no bookings, make one
   through the UI first so the page isn't empty.

## Shots

| File | Page / URL | What to show |
|---|---|---|
| `home.png` | `/` (Home) | Landing page — hero + featured/now-showing section. |
| `movie-list.png` | `/movies/` (catalog) | Movie grid with posters and the search/filter controls visible. |
| `movie-detail.png` | a movie detail page | Hero with poster, synopsis, cast/crew, and the screenings list. |
| `screening-list.png` | screenings schedule | The schedule view with several screenings across days. |
| `booking.png` | booking / seat-selection form | The reserve-seats form for a screening (seat count, price, CTA). |
| `my-bookings.png` | `/bookings/` (My bookings) | Logged-in user's bookings showing different statuses. |
| `admin.png` | `/admin/` | A populated changelist — e.g. Bookings or Movies. |
| `api-docs.png` | `/api/v1/docs/` | Swagger UI with the endpoint groups expanded. |

## Tips

- Keep the aspect ratios reasonable; the README lays them out two-per-row, so similarly
  sized images look best.
- PNG, trimmed to the content (no OS chrome). Reasonable file size (< ~500 KB each).
- Re-running `seed_db --flush --posters` reshuffles data; capture a set in one sitting so
  titles/posters are consistent across shots.
- The generated posters live under `media/` (git-ignored, regenerable) — only the
  screenshots in this folder are committed.
