# US-39 — custom 403/404/500 pages + flash polish (design)

**Milestone:** M5 — Polish (`v1.0.0`)
**User story:** US-39 — Custom 403/404/500 templates + flash messages polish
**Branch:** `feat/FR-12-error-pages`
**FR refs:** FR-12 (error handling + access control)
**Date:** 2026-05-25
**Type:** mostly mechanical (templates + 1 settings line) + one technical nuance (500 has no context).
**Predecessor:** US-38 ✅ (exhaustive translations, merged #43).

---

## 1. Goal

Replace Django's default debug/error responses with themed, translated **403 / 404 / 500**
pages, and polish the flash-message rendering (fix the broken `error` styling + add per-level
icons). The access-control half of FR-12 (`LoginRequiredMixin`, others'-booking → 403) was
already delivered in M3 (US-21) — this US is the **presentation** layer.

**Definition of done:**
1. Under `DEBUG=False`, a 404 (unknown URL), a 403 (`PermissionDenied`), and a 500
   (unhandled exception) each render the custom themed, translated template.
2. `error`-level flash messages render `alert-danger` (currently `alert-error`, unstyled);
   every level shows a leading icon.
3. New strings are translated PL/EN (the US-38 en-coverage gate enforces it).
4. Full suite + ruff/format/mypy green; coverage ≥ 80%.

## 2. Scope boundary

**In scope:**
- `templates/404.html`, `templates/403.html`, `templates/500.html` (+ a shared
  `templates/errors/_error_base.html`).
- `settings/base.py` — `MESSAGE_TAGS = {messages.ERROR: "danger"}`.
- `templates/base.html` — messages block: `message.level_tag` for the class + per-level icon.
- `en`/`pl` catalogs for the new strings.

**Out of scope:**
- Auto-dismiss / toast JS (decided against — adds timing-dependent tests for little value).
- Other status codes (400/405/etc.) — FR-12 names 403/404/500 only.
- Custom `handler403/404/500` functions — unneeded (see §3).
- Access-control logic — already done (US-21). Real deployment / static serving (post-1.0).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Template structure | A shared `errors/_error_base.html` (extends `base.html`, defines `error_code`/`error_title`/`error_text` blocks) — mirrors the existing `_auth_base.html` pattern. `403.html`/`404.html` extend it. |
| **500 is standalone** | `handler500` (`django.views.defaults.server_error`) renders `500.html` via `template.render()` with **no request and no context processors**. `base.html` needs `request`/`user`/`messages`/`csrf`, so `500.html` does **not** extend it — it's a minimal self-contained doc that links the same static CSS. (Differs from the m5_planning "extending base.html" note, which is unsafe for 500.) |
| Handler wiring | **None.** Django's default handlers auto-discover root `403.html`/`404.html`/`500.html` by name via `TEMPLATES["DIRS"]` (`BASE_DIR/"templates"`). No `handlerNNN` vars. |
| `error` → `danger` | `MESSAGE_TAGS = {messages.ERROR: "danger"}` in settings. This makes `message.level_tag` / `message.tags` emit `danger`, so `alert-{{ message.level_tag }}` is a valid Bootstrap class. Fixes all 4 `messages.error(...)` call sites at once. |
| Icons | Unicode glyphs in the template (✓ success · ✗ danger · ⚠ warning · ℹ info) via a small `{% if %}` on `message.level_tag` — matches the project's emoji style; not translated. |
| i18n source | Polish = msgid (continues US-37/38). New strings wrapped in `{% trans %}`; `en` translated; `pl` empty (msgid fallback). |
| 500 translation | `{% trans %}` best-effort — the request's active language is usually still set when the exception is rendered; otherwise it falls back to the Polish msgid (acceptable for a 500). |

## 4. Templates

**`templates/errors/_error_base.html`** — `{% extends "base.html" %}` + `{% load i18n %}`,
fills `{% block content %}` with a centered layout:
```
<div class="text-center py-5">
  <p class="display-1 ...">{% block error_code %}{% endblock %}</p>
  <h1>{% block error_title %}{% endblock %}</h1>
  <p class="text-muted">{% block error_text %}{% endblock %}</p>
  <a href="/" class="btn btn-primary mt-3">{% trans "Wróć na stronę główną" %}</a>
</div>
```
The home link is hardcoded `/` (request-independent, also works if `{% url %}` resolution is
fine — but `/` is simplest and safe everywhere).

**`templates/404.html`** — extends `errors/_error_base.html`; code `404`, title
`{% trans "Nie znaleziono strony" %}`, text "Strona, której szukasz, nie istnieje lub została
przeniesiona.".

**`templates/403.html`** — extends `errors/_error_base.html`; code `403`, title
`{% trans "Brak dostępu" %}`, text "Nie masz uprawnień, aby zobaczyć tę stronę.".

**`templates/500.html`** — standalone full HTML doc: `{% load static i18n %}`,
`<html lang="...">` (`{% get_current_language %}`), links `theme.css` + `components.css`,
centered translated message (code `500`, title "Coś poszło nie tak", text "Wystąpił błąd po
naszej stronie. Spróbuj ponownie za chwilę.") + a plain `<a href="/">` home link. **No**
`base.html`, **no** navbar/footer/switcher, **no** `{% csrf_token %}`/`request`/`messages`.

## 5. Flash polish (`templates/base.html` messages block)

Replace the alert markup with `message.level_tag` for the class and a per-level icon:
```
<div class="alert alert-{{ message.level_tag|default:'info' }} alert-dismissible fade show" role="alert">
  <span aria-hidden="true">{% if message.level_tag == 'success' %}✓{% elif message.level_tag == 'danger' %}✗{% elif message.level_tag == 'warning' %}⚠{% else %}ℹ{% endif %}</span>
  {{ message }}
  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="{% trans 'Zamknij' %}"></button>
</div>
```
`MESSAGE_TAGS` (settings) maps `ERROR` → `danger`, so error flashes now style red. (`debug`
level falls into the `ℹ` else branch — fine; it's dev-only.)

## 6. i18n

New Polish msgids: `Wróć na stronę główną`, `Nie znaleziono strony`, the 404 text,
`Brak dostępu`, the 403 text, `Coś poszło nie tak`, the 500 text. (`Zamknij` already exists
from US-38.) Run `makemessages -l en -l pl --no-wrap`, fill `en` `msgstr`s, leave `pl` empty,
`compilemessages`, commit `.po` + `.mo`. The US-38 `test_en_catalog_has_no_empty_msgstr` gate
fails if any new string is left untranslated.

**EN translations:**
```
"Wróć na stronę główną"  -> "Back to home"
"Nie znaleziono strony"  -> "Page not found"
"Strona, której szukasz, nie istnieje lub została przeniesiona." -> "The page you're looking for doesn't exist or has moved."
"Brak dostępu"           -> "Access denied"
"Nie masz uprawnień, aby zobaczyć tę stronę." -> "You don't have permission to view this page."
"Coś poszło nie tak"     -> "Something went wrong"
"Wystąpił błąd po naszej stronie. Spróbuj ponownie za chwilę." -> "Something went wrong on our side. Please try again in a moment."
```
EN strings are apostrophe-free where asserted in a test (US-37 lesson) — note "you're"/"doesn't"
contain apostrophes, so tests assert on the **403/404 title / code**, not those sentences.

## 7. Testing (Claude — `tests/test_error_pages.py`, new)

All error tests run under `@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])` —
**`testserver` is required**, or `DEBUG=False` rejects the test client's host with 400.

- **404** — `client.get("/no-such-url-xyz/")` → 404; body contains `404` and "Page not found"
  under `en` (or the Polish title under `pl`).
- **403** — reuse the US-21 path: a logged-in user GETs another user's booking detail → 403;
  body contains the 403 title. (Confirms `permission_denied` renders the custom template.)
- **500** — call the handler directly:
  `from django.views.defaults import server_error; resp = server_error(RequestFactory().get("/"))`
  → `status_code == 500`; body contains `500` / the title. This proves `500.html` renders with
  **no context** (the standalone-design guarantee), without needing a deliberately broken route.
- **flash** — assert an `error`-level message renders `alert-danger` (not `alert-error`) and the
  `✗` icon: a small request that adds `messages.error(...)` then renders a page, or assert
  `message.level_tag == "danger"` after setting `MESSAGE_TAGS` (verifies the mapping).
- **en-coverage** (existing, US-38) — guards that the new error strings are translated.

## 8. Coverage / migration

Templates + a one-line settings dict + the flash-block edit + new tests. No new app Python
logic (default handlers used) → coverage threshold unaffected. **No migration.**

## 9. Risks

1. **500 has no context** (the central nuance) — `500.html` must not use `base.html`/`request`/
   `messages`/`csrf`. Mitigation: standalone template (§4); the direct-`server_error` test proves it.
2. **`DEBUG=False` test host** — without `ALLOWED_HOSTS=["testserver"]` the client gets a 400
   `DisallowedHost`, not the error page. Mitigation: override both in §7.
3. **`DEBUG=False` static** — error pages link `static` CSS; under `DEBUG=False` the dev static
   view is off, so the `<link>` 404s in tests. Harmless (tests assert on HTML text, not CSS load);
   real serving is a deployment concern (out of scope).
4. **PyCharm hard-wrap (pitfall #6)** — keep `{% %}` tags single-line in the new templates;
   parse-check templates after editing (the US-38 lesson — it broke `base.html`).
5. **en-coverage gate** — forgetting to translate a new error string fails the suite; that's the
   gate working as intended (just fill the `msgstr`).

## 10. Build order (for the plan)

1. Tests (`tests/test_error_pages.py`) — red (no custom templates yet / `alert-error`).
2. `errors/_error_base.html` + `404.html` + `403.html` (extend base) + standalone `500.html`.
3. `settings/base.py` `MESSAGE_TAGS`; `base.html` messages block (level_tag + icons).
4. `makemessages` → fill `en` → `compilemessages`.
5. Quality gate (pytest cov ≥ 80%, ruff, ruff format, mypy).

Status board (`.Claude/backlog.md`) flips US-39 → In Progress in the first commit.
