# US-38 — PL/EN translations of all user-facing strings (design)

**Milestone:** M5 — Polish (`v1.0.0`)
**User story:** US-38 — Tłumaczenia PL/EN — wszystkie user-facing stringi
**Branch:** `feat/FR-15-translations`
**FR refs:** FR-15 (i18n PL/EN)
**Date:** 2026-05-25
**Type:** mostly mechanical (mark + translate) + one technical decision (Polish plurals).
**Predecessor:** US-37 ✅ (i18n machinery + navbar slice, merged in #42).

---

## 1. Goal

US-37 stood up the i18n pipeline and translated the navbar as a proof slice. US-38 makes the
**entire public web UI** translatable: every user-facing literal is marked and given an English
translation, so flipping the navbar switcher to EN flips the whole site (not just the navbar).

**Definition of done:**
1. Every public-web user-facing string is wrapped (`{% trans %}`/`{% blocktrans %}` in
   templates, `gettext`/`ngettext` family in Python).
2. The `en` catalog has a real `msgstr` for every one of those strings (no empty/fuzzy).
3. Switching to EN renders English across catalog, screening, booking, and auth pages
   (incl. flash messages, form errors, the activation email).
4. Counted nouns (seat counts) are grammatically correct in both languages via plural forms.
5. Full suite + ruff/format/mypy green; `tests/test_i18n.py` extended with a coverage gate,
   a plural test, and a render-smoke test.

## 2. Scope boundary

**In scope (public web UI):**
- All templates: `base.html` (footer + aria-labels left unmarked in US-37), `accounts/*`
  (7 files incl. `_auth_base.html`), `cinema/*` (3), `booking/*` (3).
- `apps/booking/views.py` — 6 Stripe/booking flash messages (currently raw Polish).
- `apps/cinema/forms.py` — `placeholder` + `empty_label`.
- `apps/booking/services.py` — 5 `BookingError` messages (shown to the user via `str(exc)`).
- `templates/accounts/emails/activation_{subject,body}.txt` — currently hard-coded English.
- `en` translations for everything above **plus** strings already wrapped but never translated:
  `BookingStatus` choices (`Oczekująca`/`Potwierdzona`/`Anulowana`), `apps/accounts/views.py`
  messages, `apps/booking/forms.py` labels/errors.

**Out of scope:**
- **Django admin** — model `verbose_name`/field labels (e.g. `_("seats count")`, staff-facing,
  many provided by Django itself). Left untouched, including the unwrapped
  `apps/accounts/models.py` `verbose_name = "user"`.
- **DRF API** — serializer labels / error messages (machine/dev-facing JSON; would need
  `Accept-Language` handling we are not adding).
- Error pages (403/404/500) → **US-39**. `i18n_patterns` on URLs → not used (FR-15: URLs stay
  English, only content is translated).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Source language | **Polish = msgid** for all UI strings (continues US-37). EN catalog gets English `msgstr`. |
| `pl` catalog (singular) | `msgstr` left **empty** → Django falls back to the Polish msgid. |
| `pl` catalog (plural) | **Filled** `msgstr[0/1/2]` — a `{% blocktrans count %}` template carries only 2 Polish forms, but Polish needs 3 (1 / 2-4 / 5+). Empty fallback would mis-render "2 miejsca" as "2 miejsc". So plural strings get the full Polish 3-form `msgstr` in `pl`; everything else stays empty. |
| Plurals | `{% blocktrans count %}` (templates) / `ngettext` family (Python). EN `nplurals=2`, PL `nplurals=3`. |
| Coverage guard | A test compiles the catalogs and asserts the `en` catalog has **no empty/fuzzy `msgstr`** for our domain (approach **C** — catches future untranslated strings). |
| EN wording | Claude-authored, apostrophe-free where the string is asserted in a test (avoids HTML-escaping fragility, per US-37). |
| `.mo` in git | **Committed** (project already un-ignores `.mo`) — CI gets compiled catalogs with no gettext step. |
| Already-English aria/brand | `base.html` `Toggle navigation`/`Close` (Bootstrap) and the `KinoMania` brand title are re-expressed as Polish msgids (`Przełącz nawigację`/`Zamknij`) so they follow the one source rule; `Powered by Django` and the `🎬 KinoMania` brand mark stay literal. |

## 4. Template layer

Add `{% load i18n %}` to every template that lacks it (all except `base.html`); for the auth
templates it goes in `_auth_base.html` and each child that has its own literals.

- **Simple literals** → `{% trans "…" %}` (buttons, headings, labels, `{% block title %}`
  overrides, `nav-pill` labels, badges).
- **Literals with variables** → `{% blocktrans %}` with `{% blocktrans with x=expr %}` to pull
  filtered values in, e.g.
  `{% blocktrans with d=effective_date|date:"d.m.Y" %}Brak seansów na dzień {{ d }}.{% endblocktrans %}`.
- **Counted nouns** → `{% blocktrans count n=booking.seats_count %}{{ n }} miejsce{% plural %}{{ n }} miejsc{% endblocktrans %}`
  (seat counts in `my_bookings.html`, etc.).
- **Already-localized by Django:** date filters like `|date:"l, j E"` render Polish/English day
  and month names automatically when the locale is active — no marking needed, do **not** wrap
  them.
- **PyCharm hard-wrap (dev pitfall #6):** keep every `{% %}`/`{{ }}` tag on one line; use
  `{% blocktrans %}` blocks rather than wrapping a long `{% trans %}`.

base.html specifics still pending from US-37: footer `educational project` text + the two
`aria-label`s, per §3.

## 5. Python layer

- `apps/booking/views.py` — wrap all 6 `messages.*` strings with `gettext_lazy as _`
  (import already conventional in the codebase). These are eager-rendered at request time;
  `gettext_lazy` is safe.
- `apps/cinema/forms.py` — wrap `placeholder` attr values and `empty_label` with
  `gettext_lazy`.
- `apps/booking/services.py` — wrap the 5 `BookingError` messages. The seat-count one
  (`NotEnoughSeatsError`) becomes **plural-aware** via `ngettext`, with a msgid identical to the
  `apps/booking/forms.py` `clean_seats_count` message so they share a single catalog entry:
  `ngettext("Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę.",
  "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę.", available) % {"count": available}`.
  `forms.py` is converted to the same plural-aware form (it currently uses a single
  `%(available)d` msgid — re-key to `%(count)d` + `ngettext` so both call sites match).
- No changes to `BookingStatus`, `accounts/views.py`, `booking/forms.py` labels beyond the
  plural re-key above — they are already wrapped; they only gain `en` `msgstr`s.

## 6. Email

`activation_subject.txt` / `activation_body.txt` are rendered via `render_to_string`
(`apps/accounts/emails.py`) and currently hard-coded English. Rewrite their bodies with Polish
source text wrapped in `{% load i18n %}` + `{% trans %}`/`{% blocktrans %}` so they localize to
the active language. The subject is a single `{% trans %}` line (`.strip()` in `emails.py` keeps
working). The 3-day validity sentence uses `{% blocktrans %}`.

> Note: the email localizes to the language **active in the request** that triggers the send
> (registration/resend). No per-user language preference is stored (out of scope).

## 7. Catalogs

- `python manage.py makemessages -l en -l pl --no-wrap --ignore=.venv` — `--no-wrap` keeps `.po`
  diffs line-stable. Extracts from templates + Python into both `django.po` files.
- **`en/django.po`:** fill every `msgstr` (singular) and `msgstr[0]`/`msgstr[1]` (plural) with
  English. Confirm header `Plural-Forms: nplurals=2; plural=(n != 1);`.
- **`pl/django.po`:** leave singular `msgstr` empty (msgid fallback); fill plural
  `msgstr[0/1/2]` with the correct Polish forms. Set header
  `Plural-Forms: nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);`.
- De-fuzz any entries `makemessages` marks fuzzy; remove obsolete `#~` entries.
- `python manage.py compilemessages` → `.mo` (commit `.po` + `.mo`).

**Execution prerequisite:** gettext tools on PATH (resolved in US-37 — mlocati gettext-iconv at
`/c/Program Files/gettext-iconv/bin/`, dev pitfall #25).

The **full string inventory** (every msgid + its EN msgstr, grouped by file) is enumerated in
the implementation plan, not here.

## 8. Testing (Claude writes — extend `tests/test_i18n.py`)

Building on US-37's 4 tests:
- **`test_en_catalog_has_no_empty_msgstr`** — parse `locale/en/LC_MESSAGES/django.po` with a
  small dependency-free parser in the test (no `polib` — not installed, and not worth a new dev
  dep for one test) and assert every non-header entry has a non-empty `msgstr` / all plural
  `msgstr[*]` filled, and none are `fuzzy`. This is the approach-C regression gate.
- **`test_seat_count_plural_en`** — under `activate("en")`, the seat-count string renders
  `1 seat` / `2 seats` / `5 seats`; under `pl`, `1 miejsce` / `2 miejsca` / `5 miejsc`
  (exercises both plural tables).
- **`test_booking_page_translates`** (`@pytest.mark.django_db`) — a booking/catalog page that
  was raw Polish in US-37 now shows known English text after switching to `en` (e.g. the
  "Razem"→"Total" / "Zarezerwuj i zapłać"→… button), and the Polish original under `pl`.
- Keep assertions on **translated UI strings**, never on locale-formatted numbers/dates
  (dev pitfalls #4/#5).

## 9. Coverage / migration

Template/Python string marking + locale files + tests. The Python edits are string wrapping
(no new branches/logic) → coverage threshold (≥80%) unaffected. **No migration.**

## 10. Risks

1. **Plural fallback trap** — leaving PL plural `msgstr` empty silently mis-renders 2-4 counts.
   Mitigation: §3 fills PL plural forms; `test_seat_count_plural_en` covers `pl` too.
2. **`msgid` drift between `forms.py` and `services.py`** — the two seat-count messages must be
   byte-identical to share a catalog entry. Mitigation: §5 re-keys both to the same `%(count)d`
   ngettext pair; the coverage test would otherwise show a second untranslated entry.
3. **PyCharm hard-wrap** breaking `{% %}` tags (dev pitfall #6) — single-line tags / blocktrans.
4. **`.po`/`.mo` drift** — editing `.po` without `compilemessages` ships stale `.mo`. Mitigation:
   committed `.mo` + the en-coverage test reads `.po` (source of truth), and a render test reads
   `.mo` (compiled) — divergence fails.
5. **`{% blocktrans %}` + filters** — filters can't be applied inside the block; must be hoisted
   via `{% blocktrans with x=val|filter %}`. Easy to miss → `TemplateSyntaxError` caught by tests.
6. **HTML-escaping in test assertions** — apostrophes/quotes in EN strings escape in rendered
   HTML; keep test-asserted EN strings apostrophe-free (US-37 lesson).

## 11. Build order (for the plan)

1. Templates: `{% load i18n %}` + mark all literals (base.html remainder, accounts, cinema,
   booking), plurals via `{% blocktrans count %}`.
2. Python: `booking/views.py`, `cinema/forms.py`, `booking/services.py` (+ `forms.py` re-key).
3. Email templates.
4. `makemessages` → fill `en` (all) + `pl` (plurals only) → `compilemessages`.
5. Tests: en-coverage gate, plural test, page-translation smoke (extend `tests/test_i18n.py`).
6. Quality gate (pytest cov ≥ 80%, ruff, ruff format, mypy).

Status board (`.Claude/backlog.md`) flips US-38 → In Progress as part of the first commit.
