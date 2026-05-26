# UI redesign — prototype handoff integration

- **Type:** style/infra · **Branch:** `feat/ui-redesign`
- **Source:** `templates_new/` handoff pack (from "KinoMania Prototype.html")
- **Date:** 2026-05-26 · **Scope:** post-M4 UI polish (not in the original backlog)

## Goal

Wire the prototype handoff pack into the live templates: a new additive `addons.css`, a set
of `.km-*` components (status badges, ticket, booking-row, date-chip strip, summary rail,
styled error pages), and the templates that use them. No model/business-logic changes; the
seat picker is intentionally out of the pack.

## Areas restyled (5)

| Page | Change |
|---|---|
| `cinema/screening_list.html` | `.km-datestrip` day chips (needs `available_dates`) + per-seat price subline on the time pills (`.time-pill__price`) |
| `booking/my_bookings.html` | `.km-tabs` (underline tabs) + `.km-brow` rows with poster, status `.km-badge`, pay/cancel actions |
| `booking/booking_detail.html` | `.km-ticket` (perforated ticket) + success-circle for CONFIRMED + `.km-dl` details + genres line |
| `booking/booking_form.html` | 2-column layout with sticky `.km-summary` rail and live total |
| `403/404/500.html` | `.km-error` styling |

Plus `static/css/addons.css` (new) and `templates/_partials/booking_badge.html` (a reusable
status-badge include shipped by the pack; available but not yet wired — `my_bookings`/
`booking_detail` still inline their badge).

## Key decisions

| Decision | Choice / why |
|---|---|
| **`500.html` stays standalone** | The pack's `500.html` extended `_error_base` → `base.html`, but `django.views.defaults.server_error` renders with **no** RequestContext (no request/user/messages/csrf/context-processors). Kept `500.html` standalone (own `<html>`, links `theme.css` + `addons.css`, `.km-error` body) — preserves the US-39 design and the `test_500_renders_custom_template` contract. **403/404 use the pack versions** (those handlers pass the request). |
| **Price back on the screening list** | The pack adds `{{ s.price }} zł` to the time pills, **reversing the US-21 decision** to keep price off the list. Honoured the pack (it's the intended design); updated `test_screening_pill_shows_hour_grouped_by_hall` accordingly. |
| **`available_dates` in the view** | `ScreeningListView.get_context_data` now passes today + next 6 days (`is_today`/`is_tomorrow` flags) so the date strip renders. Degrades gracefully — the date `<input>` still works. |
| **Genres prefetch** | `booking_detail` ticket lists genres; added `prefetch_related("screening__movie__genres")` to `BookingDetailView` so the render-time query stays within the existing budget (5). |
| **`addons.css` link** | Added once in `base.html` after `components.css`; also linked directly in standalone `500.html`. Pure additive — all values come from `theme.css` vars. |

## i18n

New Polish msgids introduced by the pack (`Bilet`, `Numer rezerwacji`, `Podsumowanie`,
`Razem`, `Dziś`, `Jutro`, `Wybierz dzień`, `Rezerwacja potwierdzona!`, `Bilety wysłaliśmy…`,
`Wróć do repertuaru`, the reworded error-page text, …). Ran `makemessages -l pl -l en`
(ignoring `templates_new/`), filled the **14** new/fuzzy EN msgstrs, `compilemessages`.
The US-38 EN coverage gate (`test_en_catalog_has_no_empty_msgstr`) is green (0 empty, 0
fuzzy). PL singular msgstrs left empty by design (fallback to the Polish msgid).

## Out of scope

- `movie_list.html` / `movie_detail.html` — not in the pack; catalog grid + detail hero keep
  their current look. `addons.css` carries unused `.movie-card__badge` / `.movie-hero__rating`
  classes for a future pass (would also need `Movie.is_new`/rating).
- Interactive seat picker (needs a `Seat` model + backend — excluded by the pack).
- A real QR generator (the ticket shows a static `QR` placeholder).
- `booking.reference` slug (ticket uses `KM-{id}`).

## Verification

- `pytest` — **561 passed**, coverage 99% (incl. all render/budget/i18n tests).
- `ruff check` / `ruff format --check` / `mypy` — clean on changed Python.
- EN catalog: 0 empty, 0 fuzzy; `compilemessages` clean.
