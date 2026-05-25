# US-38 — PL/EN translations of all user-facing strings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark and translate every public-web user-facing string PL→EN, so flipping the navbar switcher to EN flips the whole site (catalog, screenings, booking, auth, flash messages, the activation email), with grammatically correct Polish/English plurals.

**Architecture:** Polish stays the msgid (source) — continues US-37. Templates wrap literals in `{% trans %}`/`{% blocktrans %}` (incl. `{% blocktrans count %}` for counted nouns); Python wraps flash messages, form bits, and `BookingError`s with the `gettext` family. `makemessages` extracts into `locale/{en,pl}/LC_MESSAGES/django.po`; the **en** catalog gets full English `msgstr`s; the **pl** catalog stays empty except plural entries (which need all 3 Polish forms). `.mo` is committed. A `.po`-parsing test gates against untranslated strings.

**Tech Stack:** Django i18n (`{% trans %}`, `{% blocktrans %}`/`count`, `gettext`/`ngettext`, gettext tooling); pytest / pytest-django.

---

## Role division

- **User** writes app files (`templates/**`, `apps/**/*.py`, `locale/**`) and runs all `git`/`pytest`/`manage.py` commands.
- **Claude** writes all test code (`tests/**`).

## Spec

`docs/superpowers/specs/2026-05-25-us38-translations-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `tests/test_i18n.py` | modify | + en-coverage gate, plural test, page-translation smoke | Claude |
| `templates/base.html` | modify | footer + 2 aria-labels | User |
| `templates/accounts/{login,register,resend,resend_done,activation_sent,activation_invalid}.html` | modify | `{% load i18n %}` + mark literals | User |
| `templates/cinema/{movie_list,movie_detail,screening_list}.html` | modify | `{% load i18n %}` + mark literals (+ plurals) | User |
| `templates/booking/{my_bookings,booking_form,booking_detail}.html` | modify | `{% load i18n %}` + mark literals (+ plurals) | User |
| `templates/accounts/emails/activation_{subject,body}.txt` | modify | Polish source wrapped in i18n | User |
| `apps/booking/views.py` | modify | wrap 6 flash messages | User |
| `apps/cinema/forms.py` | modify | wrap placeholders + empty_label | User |
| `apps/booking/services.py` | modify | wrap 5 BookingError messages (seat-count → ngettext) | User |
| `apps/booking/forms.py` | modify | re-key seat-availability error to shared ngettext | User |
| `locale/en/LC_MESSAGES/django.{po,mo}` | modify | full English translations (committed) | User |
| `locale/pl/LC_MESSAGES/django.{po,mo}` | modify | plural forms filled; rest empty (committed) | User |
| `.Claude/backlog.md` | modify | status board → US-38 In Progress | User |

No migration. `templates/accounts/_auth_base.html` is **not** touched (it has no literals — brand text only).

## TDD note

Translation isn't a red-green-per-string loop. The TDD shape here: write the three new tests first (Task 1) — they go **red** (no en catalog entries yet / Polish still rendering) — then marking (Tasks 2-5) + catalog (Task 6) turn them **green**. The en-coverage test is the durable regression gate: any future untranslated string fails it.

Run tests with `--no-cov` during the loop for speed; the final coverage gate (Task 7) runs the full suite.

---

### Task 1: Extend the i18n tests (red)

**Files:**
- Modify: `tests/test_i18n.py`

- [ ] **Step 1 [Claude]: Append the new tests + a tiny `.po` parser**

Append to `tests/test_i18n.py` (keep the existing US-37 tests above):

```python
import re

from django.utils import translation
from django.utils.translation import ngettext


def _po_blocks(path):
    """Yield raw line-lists for each entry in a .po file (split on blank lines)."""
    raw = path.read_text(encoding="utf-8")
    for chunk in raw.split("\n\n"):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if lines:
            yield lines


def _msgstr_empty(lines, idx):
    """True if the msgstr starting at lines[idx] (incl. continuation rows) is empty."""
    m = re.match(r'^msgstr(?:\[\d+\])? "(.*)"$', lines[idx])
    if m and m.group(1):
        return False
    j = idx + 1
    while j < len(lines) and lines[j].startswith('"'):
        if lines[j].strip('"'):
            return False
        j += 1
    return True


def test_en_catalog_has_no_empty_msgstr():
    """Approach-C gate: every en entry is translated and non-fuzzy."""
    po = settings.BASE_DIR / "locale" / "en" / "LC_MESSAGES" / "django.po"
    assert po.exists(), "run makemessages + translate the en catalog"
    problems = []
    for lines in _po_blocks(po):
        is_header = lines[0].startswith("msgid \"\"") and not any(
            ln.startswith("msgid_plural") for ln in lines
        )
        if is_header:
            continue
        if any(ln.startswith("#,") and "fuzzy" in ln for ln in lines):
            problems.append(("fuzzy", lines[:3]))
            continue
        for idx, ln in enumerate(lines):
            if ln.startswith("msgstr") and _msgstr_empty(lines, idx):
                problems.append(("empty", lines[:3]))
                break
    assert not problems, f"untranslated/fuzzy en entries: {problems}"


def test_seat_count_plural_display():
    """blocktrans-count seat label: 2 EN forms, 3 PL forms (the pl-fill regression)."""
    s, p = "%(counter)s miejsce", "%(counter)s miejsc"
    with translation.override("en"):
        assert ngettext(s, p, 1) % {"counter": 1} == "1 seat"
        assert ngettext(s, p, 2) % {"counter": 2} == "2 seats"
        assert ngettext(s, p, 5) % {"counter": 5} == "5 seats"
    with translation.override("pl"):
        assert ngettext(s, p, 1) % {"counter": 1} == "1 miejsce"
        assert ngettext(s, p, 2) % {"counter": 2} == "2 miejsca"
        assert ngettext(s, p, 5) % {"counter": 5} == "5 miejsc"


def test_catalog_page_translated_en(client):
    """A real public page renders US-38 strings in English after switching."""
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    body = client.get("/").content.decode()
    assert "Now Showing" in body  # navbar (US-37)
    assert "Search" in body       # filter label (US-38)
    assert "Filter" in body       # filter button (US-38)
    assert "Szukaj" not in body   # Polish source no longer leaking
```

> Note: `settings` and `reverse` are already imported at the top of the file from US-37; `pytestmark = pytest.mark.django_db` already applies, so the `client` tests hit the DB fine.

- [ ] **Step 2 [User]: Run to confirm FAIL**

Run: `poetry run pytest tests/test_i18n.py -q --no-cov`
Expected: the 3 new tests FAIL — `test_en_catalog_has_no_empty_msgstr` (no US-38 msgids translated yet / entries empty), `test_seat_count_plural_display` (msgid not in catalog → returns the Polish msgid, so EN assert fails), `test_catalog_page_translated_en` ("Search" not present — page still Polish). The 4 US-37 tests stay green.

---

### Task 2: Mark `base.html` remainder + accounts templates

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/accounts/{login,register,resend,resend_done,activation_sent,activation_invalid}.html`

> Keep every `{% trans %}`/`{% blocktrans %}` tag on **one line** (PyCharm hard-wrap breaks `{% %}`, dev pitfall #6).

- [ ] **Step 1 [User]: `base.html` — 3 edits**

`{% load static i18n %}` is already present (US-37). Apply:

The toggler button `aria-label`:
```html
                aria-label="{% trans 'Przełącz nawigację' %}">
```
The alert close button `aria-label` (inside the messages loop):
```html
                data-bs-dismiss="alert" aria-label="{% trans 'Zamknij' %}"></button>
```
The footer brand span:
```html
        <span>🎬 © 2026 KinoMania · {% trans "projekt edukacyjny" %}</span>
```

- [ ] **Step 2 [User]: `accounts/login.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Logowanie" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Zaloguj się, żeby zarezerwować bilety" %}{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">{% trans "Logowanie" %}</h2>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% for error in field.errors %}
        <div class="auth-card__field-error">{{ error }}</div>
        {% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">{% trans "Zaloguj się" %}</button>
</form>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    <a href="{% url 'accounts:activation_resend' %}">{% trans "Nie dostałeś emaila aktywacyjnego?" %}</a>
    <div class="auth-footer-link__divider"></div>
    {% trans "Nie masz konta?" %} <a href="{% url 'accounts:register' %}">{% trans "Zarejestruj się" %}</a>
</div>
{% endblock %}
```

- [ ] **Step 3 [User]: `accounts/register.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Rejestracja" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Stwórz konto i zacznij rezerwować" %}{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">{% trans "Rejestracja" %}</h2>
<p class="auth-card__hint">{% trans "Po wysłaniu formularza otrzymasz email z linkiem aktywacyjnym." %}</p>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% if field.help_text %}
        <div class="auth-card__field-help">{{ field.help_text|safe }}</div>
        {% endif %}
        {% for error in field.errors %}
        <div class="auth-card__field-error">{{ error }}</div>
        {% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">{% trans "Zarejestruj się" %}</button>
</form>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    {% trans "Masz już konto?" %} <a href="{% url 'accounts:login' %}">{% trans "Zaloguj się" %}</a>
</div>
{% endblock %}
```

- [ ] **Step 4 [User]: `accounts/resend.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Wyślij ponownie link" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Wyślij ponownie link aktywacyjny" %}{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">{% trans "Wyślij ponownie" %}</h2>
<p class="auth-card__hint">{% trans "Wpisz email użyty przy rejestracji — jeśli konto czeka na aktywację, wyślemy nowy link." %}</p>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% for error in field.errors %}
        <div class="auth-card__field-error">{{ error }}</div>
        {% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">{% trans "Wyślij" %}</button>
</form>
{% endblock %}
```

> The original `<h2>Resend</h2>` is changed to a Polish msgid (`Wyślij ponownie`) so it follows the one-source rule; its EN msgstr is `Resend` (Task 6).

- [ ] **Step 5 [User]: `accounts/resend_done.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Wysłane" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Wysłane" %}{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">📨</div>
    <p class="auth-card__message-text">{% trans "Jeśli konto o podanym adresie email istnieje i nie zostało jeszcze aktywowane, wysłaliśmy nowy link aktywacyjny." %}</p>
    <p class="auth-card__message-hint">{% trans "Link jest ważny przez 3 dni." %}</p>
</div>
{% endblock %}
```

- [ ] **Step 6 [User]: `accounts/activation_sent.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Sprawdź skrzynkę" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Email wysłany" %}{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">📬</div>
    <p class="auth-card__message-text">{% trans "Wysłaliśmy link aktywacyjny na podany adres. Kliknij w niego, aby aktywować konto." %}</p>
    <p class="auth-card__message-hint">{% trans "Link jest ważny przez 3 dni. Nie widzisz emaila? Sprawdź folder spam." %}</p>
</div>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    <a href="{% url 'accounts:activation_resend' %}">{% trans "Wyślij link ponownie" %}</a>
</div>
{% endblock %}
```

- [ ] **Step 7 [User]: `accounts/activation_invalid.html`**

```html
{% extends "accounts/_auth_base.html" %}
{% load i18n %}

{% block title %}{% trans "Link nieprawidłowy" %} — KinoMania{% endblock %}
{% block auth_tagline %}{% trans "Link nieprawidłowy lub wygasł" %}{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">⚠️</div>
    <p class="auth-card__message-text">{% trans "Link aktywacyjny jest nieprawidłowy lub wygasł." %}</p>
    <p class="auth-card__message-hint">{% trans "Możliwe przyczyny: link został już użyty, hasło zostało w międzyczasie zmienione, albo link jest starszy niż 3 dni." %}</p>
    <div class="mt-4">
        <a href="{% url 'accounts:activation_resend' %}" class="btn btn-primary">{% trans "Wyślij link ponownie" %}</a>
    </div>
</div>
{% endblock %}
```

---

### Task 3: Mark cinema templates

**Files:**
- Modify: `templates/cinema/{movie_list,movie_detail,screening_list}.html`

- [ ] **Step 1 [User]: `cinema/movie_list.html`**

```html
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Repertuar" %} — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1">{% trans "Repertuar" %}</h1>
<p class="text-muted small mb-4">{% trans "Wszystkie filmy z zaplanowanymi seansami" %}</p>

<form method="get" class="filter-bar" role="search">
    <div style="flex:2; min-width:200px;">
        <label for="id_q">{% trans "Szukaj" %}</label>
        {{ filter_form.q }}
    </div>
    <div style="flex:1; min-width:140px;">
        <label for="id_genre">{% trans "Gatunek" %}</label>
        {{ filter_form.genre }}
    </div>
    <div style="flex:1; min-width:140px;">
        <label for="id_date">{% trans "Data" %}</label>
        {{ filter_form.date }}
    </div>
    <button type="submit" class="btn btn-primary">{% trans "Filtruj" %}</button>
    {% if request.GET %}
    <a href="{% url 'cinema:movie_list' %}"
       class="btn btn-outline-light"
       title="{% trans 'Wyczyść filtry' %}"
       aria-label="{% trans 'Wyczyść filtry' %}">×</a>
    {% endif %}
</form>

{% if movies %}
<div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-xl-5 g-3">
    {% for movie in movies %}
    <div class="col">
        <a href="{{ movie.get_absolute_url }}" class="movie-card">
            {% if movie.poster %}
            <img src="{{ movie.poster.url }}" alt="{{ movie.title }}" class="movie-card__img">
            {% else %}
            <div class="movie-card__placeholder" aria-hidden="true">🎬</div>
            {% endif %}
            <div class="movie-card__overlay">
                <div class="movie-card__title">{{ movie.title }}</div>
                <div class="movie-card__meta">
                    {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %} · {% endif %}{% endfor %}
                </div>
            </div>
        </a>
    </div>
    {% endfor %}
</div>

{% if is_paginated %}
<nav aria-label="{% trans 'Paginacja' %}" class="mt-4">
    <ul class="pagination justify-content-center">
        {% if page_obj.has_previous %}
        <li class="page-item">
            <a class="page-link"
               href="?{% querystring page=page_obj.previous_page_number %}"
               aria-label="{% trans 'Poprzednia strona' %}">«</a>
        </li>
        {% endif %}
        <li class="page-item active" aria-current="page">
            <span class="page-link">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
        </li>
        {% if page_obj.has_next %}
        <li class="page-item">
            <a class="page-link"
               href="?{% querystring page=page_obj.next_page_number %}"
               aria-label="{% trans 'Następna strona' %}">»</a>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}
{% else %}
<div class="alert alert-info">
    {% if request.GET %}
    {% trans "Brak filmów pasujących do wybranych kryteriów." %}
    {% url 'cinema:movie_list' as ml_url %}
    {% blocktrans %}<a href="{{ ml_url }}">Wyczyść filtry</a> żeby zobaczyć wszystkie.{% endblocktrans %}
    {% else %}
    {% trans "Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!" %}
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2 [User]: `cinema/movie_detail.html`**

```html
{% extends "base.html" %}
{% load i18n %}

{% block title %}{{ movie.title }} — KinoMania{% endblock %}

{% block content %}
<article>
    <section class="movie-hero">
        {% if movie.poster %}
        <div class="movie-hero__bg" style="background-image: url('{{ movie.poster.url }}');"></div>
        {% endif %}
        <div class="movie-hero__inner">
            <div class="movie-hero__poster">
                {% if movie.poster %}
                <img src="{{ movie.poster.url }}" alt="{{ movie.title }}">
                {% else %}
                <div class="movie-hero__poster-placeholder" aria-hidden="true">🎬</div>
                {% endif %}
            </div>
            <div class="movie-hero__body">
                <a href="{% url 'cinema:movie_list' %}" class="movie-hero__breadcrumb">← {% trans "Repertuar" %}</a>
                <h1 class="movie-hero__title">{{ movie.title }}</h1>
                <div class="movie-hero__meta">
                    {{ movie.duration_minutes }} min · {% blocktrans with d=movie.release_date|date:"d.m.Y" %}Premiera {{ d }}{% endblocktrans %}{% if movie.directors.all %} · {% trans "Reż." %} {% for d in movie.directors.all %}{{ d.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% endif %}
                </div>
                <div class="mb-3">
                    {% for genre in movie.genres.all %}<span class="movie-hero__genre-badge">{{ genre.name }}</span>{% endfor %}
                </div>
                <p class="movie-hero__description">{{ movie.description|linebreaksbr }}</p>
                {% if movie.actors.all %}
                <p class="movie-hero__cast">
                    <strong>{% trans "Obsada:" %}</strong>
                    {% for a in movie.actors.all|slice:":6" %}{{ a.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% if movie.actors.all|length > 6 %} {% trans "i inni" %}{% endif %}
                </p>
                {% endif %}
            </div>
        </div>
    </section>

    {% if trailer_embed_url %}
    <section class="mb-5">
        <h2 class="mb-3">{% trans "Zwiastun" %}</h2>
        <iframe src="{{ trailer_embed_url }}"
                title="{% blocktrans with t=movie.title %}Zwiastun: {{ t }}{% endblocktrans %}"
                width="100%"
                style="aspect-ratio: 16/9; border-radius: var(--radius-md); border: 0;"
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                referrerpolicy="strict-origin-when-cross-origin"
                sandbox="allow-scripts allow-same-origin allow-presentation"
                allowfullscreen></iframe>
    </section>
    {% elif movie.trailer_url %}
    <section class="mb-5">
        <h2 class="mb-3">{% trans "Zwiastun" %}</h2>
        <a href="{{ movie.trailer_url }}"
           class="btn btn-outline-light"
           target="_blank"
           rel="noopener noreferrer">{% trans "Zobacz zwiastun (link zewnętrzny)" %}</a>
    </section>
    {% endif %}

    {% if movie.directors.all %}
    <section class="mb-5">
        <h2 class="mb-3">{% trans "Reżyseria" %}</h2>
        <div class="row row-cols-2 row-cols-md-4 g-3">
            {% for director in movie.directors.all %}
            <div class="col text-center">
                {% if director.photo %}
                <img src="{{ director.photo.url }}"
                     alt="{{ director.full_name }}"
                     class="rounded-circle mb-2"
                     style="width:80px; height:80px; object-fit:cover; border:2px solid var(--border);">
                {% else %}
                <div class="rounded-circle d-flex align-items-center justify-content-center mb-2 mx-auto"
                     style="width:80px; height:80px; font-size:2rem; background:var(--bg-elev); border:2px solid var(--border);"
                     aria-hidden="true">👤
                </div>
                {% endif %}
                <div class="small">{{ director.full_name }}</div>
            </div>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {% if movie.actors.all %}
    <section class="mb-5">
        <h2 class="mb-3">{% trans "Obsada" %}</h2>
        <div id="actorsCarousel" class="carousel slide bg-elev-card" data-bs-ride="false">
            <div class="carousel-inner">
                {% for actor in movie.actors.all %}
                <div class="carousel-item {% if forloop.first %}active{% endif %}">
                    <div class="text-center py-4">
                        {% if actor.photo %}
                        <img src="{{ actor.photo.url }}"
                             alt="{{ actor.full_name }}"
                             class="rounded-circle mb-2"
                             style="width:140px; height:140px; object-fit:cover; border:2px solid var(--border);">
                        {% else %}
                        <div class="rounded-circle d-flex align-items-center justify-content-center mb-2 mx-auto"
                             style="width:140px; height:140px; font-size:3rem; background:var(--bg); border:2px solid var(--border);"
                             aria-hidden="true">👤
                        </div>
                        {% endif %}
                        <div>{{ actor.full_name }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            <button class="carousel-control-prev" type="button"
                    data-bs-target="#actorsCarousel" data-bs-slide="prev">
                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                <span class="visually-hidden">{% trans "Poprzedni" %}</span>
            </button>
            <button class="carousel-control-next" type="button"
                    data-bs-target="#actorsCarousel" data-bs-slide="next">
                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                <span class="visually-hidden">{% trans "Następny" %}</span>
            </button>
        </div>
    </section>
    {% endif %}

    <section class="mb-5">
        <h2 class="mb-3">{% trans "Nadchodzące seanse" %}</h2>
        {% if upcoming_screenings %}
        {% regroup upcoming_screenings by start_time|date:"Y-m-d" as date_groups %}
        {% for date_group in date_groups %}
        <div class="screening-day">
            <div class="screening-day__date">{{ date_group.list.0.start_time|date:"l, j E" }}</div>
            {% regroup date_group.list|dictsort:"hall.name" by hall.name as hall_groups %}
            {% for hall_group in hall_groups %}
            <div class="mt-2">
                <div class="time-pill-hall-label">{% blocktrans with name=hall_group.grouper %}Sala {{ name }}{% endblocktrans %}</div>
                <div class="time-pill-group">
                    {% for s in hall_group.list %}{% if s.is_available %}<a href="{% url 'booking:create' pk=s.pk %}" class="time-pill">{{ s.start_time|date:"H:i" }}</a>{% else %}<span class="time-pill is-soldout">{{ s.start_time|date:"H:i" }}</span>{% endif %}{% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        {% else %}
        <div class="alert alert-info">{% trans "Brak zaplanowanych seansów dla tego filmu." %}</div>
        {% endif %}
    </section>
</article>
{% endblock %}
```

- [ ] **Step 3 [User]: `cinema/screening_list.html`**

```html
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Seanse" %} — {{ effective_date|date:"d.m.Y" }} — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1">{% trans "Seanse" %}</h1>
<p class="text-muted small mb-4">{{ effective_date|date:"l, j E Y" }}</p>

<form method="get" class="filter-bar" role="search">
    <div>
        <label for="date-input">{% trans "Data" %}</label>
        <input type="date" id="date-input" name="date"
               min="{{ today|date:'Y-m-d' }}"
               max="{{ max_date|date:'Y-m-d' }}"
               value="{{ effective_date|date:'Y-m-d' }}">
    </div>
    <button type="submit" class="btn btn-primary">{% trans "Pokaż" %}</button>
    {% if request.GET.date %}
    <a href="{% url 'cinema:screening_list' %}"
       class="btn btn-outline-light"
       title="{% trans 'Wróć do dzisiejszego dnia' %}">{% trans "Dzisiaj" %}</a>
    {% endif %}
</form>

{% if movie_groups %}
{% for movie, screenings in movie_groups %}
<div class="screening-card">
    <div class="screening-card__poster">
        {% if movie.poster %}
        <img src="{{ movie.poster.url }}" alt="{{ movie.title }}">
        {% else %}
        <div class="screening-card__poster-placeholder" aria-hidden="true">🎬</div>
        {% endif %}
    </div>
    <div class="screening-card__body">
        <a href="{{ movie.get_absolute_url }}" class="screening-card__title">{{ movie.title }}</a>
        <div class="screening-card__meta">
            {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %} · {% endif %}{% endfor %} · {{ movie.duration_minutes }} min
        </div>

        {% regroup screenings|dictsort:"hall.name" by hall.name as hall_groups %}
        {% for hall_group in hall_groups %}
        <div class="mt-3">
            <div class="time-pill-hall-label">{% blocktrans with name=hall_group.grouper %}Sala {{ name }}{% endblocktrans %}</div>
            <div class="time-pill-group">
                {% for s in hall_group.list %}
                {% if s.is_available %}<a href="{% url 'booking:create' pk=s.pk %}" class="time-pill">{{ s.start_time|date:"H:i" }}</a>{% else %}<span class="time-pill is-soldout">{{ s.start_time|date:"H:i" }}</span>{% endif %}
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endfor %}
{% else %}
<div class="alert alert-info">
    {% blocktrans with d=effective_date|date:"d.m.Y" %}Brak seansów na dzień {{ d }}.{% endblocktrans %}
</div>
{% endif %}
{% endblock %}
```

---

### Task 4: Mark booking templates

**Files:**
- Modify: `templates/booking/{my_bookings,booking_form,booking_detail}.html`

- [ ] **Step 1 [User]: `booking/my_bookings.html`**

```html
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<article class="container py-4">
    <h1 class="mb-4">{% trans "Moje rezerwacje" %}</h1>

    <ul class="nav nav-pills mb-4">
        <li class="nav-item">
            <a class="nav-link {% if active_tab == 'upcoming' %}active{% endif %}" href="?tab=upcoming">{% trans "Nadchodzące" %}</a>
        </li>
        <li class="nav-item">
            <a class="nav-link {% if active_tab == 'history' %}active{% endif %}" href="?tab=history">{% trans "Historia" %}</a>
        </li>
    </ul>

    {% if bookings %}
    <div class="row row-cols-1 g-3">
        {% for booking in bookings %}
        <div class="col">
            <div class="card">
                <div class="card-body d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <div>
                        <a href="{% url 'booking:detail' pk=booking.pk %}" class="h6 text-decoration-none">{{ booking.screening.movie.title }}</a>
                        <div class="text-muted small">{{ booking.screening.start_time|date:"d.m.Y H:i" }} · {% blocktrans with name=booking.screening.hall.name %}Sala {{ name }}{% endblocktrans %} · {% blocktrans count counter=booking.seats_count %}{{ counter }} miejsce{% plural %}{{ counter }} miejsc{% endblocktrans %} · {{ booking.total_price }} zł</div>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge {% if booking.status == 'PENDING' %}bg-warning text-dark{% elif booking.status == 'CONFIRMED' %}bg-success{% else %}bg-secondary{% endif %}">{{ booking.get_status_display }}</span>
                        {% if booking.can_be_cancelled %}
                        <form method="post" action="{% url 'booking:cancel' pk=booking.pk %}" class="d-inline">{% csrf_token %}
                            <button type="submit" class="btn btn-sm btn-outline-danger">{% trans "Anuluj" %}</button>
                        </form>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="alert alert-info">{% if active_tab == 'history' %}{% trans "Brak historycznych rezerwacji." %}{% else %}{% url 'cinema:movie_list' as ml_url %}{% blocktrans %}Nie masz nadchodzących rezerwacji. <a href="{{ ml_url }}">Przeglądaj repertuar</a>.{% endblocktrans %}{% endif %}</div>
    {% endif %}
</article>
{% endblock %}
```

- [ ] **Step 2 [User]: `booking/booking_form.html`**

Only the markup head changes; the `<script>` block at the bottom stays byte-for-byte identical (don't translate JS string literals — they're DOM ids / number formatting).

```html
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<article class="container py-4" style="max-width: 640px;">
    <a href="{{ screening.movie.get_absolute_url }}" class="text-decoration-none">← {{ screening.movie.title }}</a>
    <h1 class="mt-2 mb-4">{% trans "Rezerwacja" %}</h1>

    <div class="card mb-4">
        <div class="card-body">
            <h2 class="h5 card-title">{{ screening.movie.title }}</h2>
            <dl class="row mb-0">
                <dt class="col-5">{% trans "Termin" %}</dt>
                <dd class="col-7">{{ screening.start_time|date:"d.m.Y H:i" }}</dd>
                <dt class="col-5">{% trans "Sala" %}</dt>
                <dd class="col-7">{{ screening.hall.name }}</dd>
                <dt class="col-5">{% trans "Cena za miejsce" %}</dt>
                <dd class="col-7">{{ screening.price }} zł</dd>
                <dt class="col-5">{% trans "Dostępne miejsca" %}</dt>
                <dd class="col-7">{{ screening.available_seats_count }}</dd>
            </dl>
        </div>
    </div>

    <form method="post" novalidate>
        {% csrf_token %}
        {% if form.non_field_errors %}
        <div class="alert alert-danger">{{ form.non_field_errors }}</div>
        {% endif %}
        <div class="mb-3">
            <label for="{{ form.seats_count.id_for_label }}" class="form-label">{{ form.seats_count.label }}</label>
            {{ form.seats_count }}
            {% if form.seats_count.errors %}
            <div class="text-danger small mt-1">{{ form.seats_count.errors }}</div>
            {% endif %}
        </div>
        <p class="fs-5">{% trans "Razem:" %} <strong id="booking-total">—</strong> zł</p>
        <button type="submit" class="btn btn-primary">{% trans "Zarezerwuj i zapłać" %}</button>
    </form>
</article>

<script>
    (function () {
        var price = parseFloat("{{ screening.price|stringformat:'f' }}");
        var input = document.getElementById("{{ form.seats_count.id_for_label }}");
        var out = document.getElementById("booking-total");

        function update() {
            var n = parseInt(input.value, 10);
            out.textContent = (n > 0) ? (price * n).toFixed(2) : "—";
        }

        input.addEventListener("input", update);
        update();
    })();
</script>
{% endblock %}
```

- [ ] **Step 3 [User]: `booking/booking_detail.html`**

Preserve the existing (quirky) status-badge markup exactly — only wrap the literals:

```html
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<article class="container py-4" style="max-width: 640px;">
  <h1 class="mb-4">{% blocktrans with id=booking.id %}Rezerwacja #{{ id }}{% endblocktrans %}</h1>

  <div class="card">
    <div class="card-body">
      <h2 class="h5 card-title">{{ booking.screening.movie.title }}</h2>
      <dl class="row mb-0">
        <dt class="col-5">{% trans "Termin" %}</dt><dd class="col-7">{{ booking.screening.start_time|date:"d.m.Y H:i" }}</dd>
        <dt class="col-5">{% trans "Sala" %}</dt><dd class="col-7">{{ booking.screening.hall.name }}</dd>
        <dt class="col-5">{% trans "Liczba miejsc" %}</dt><dd class="col-7">{{ booking.seats_count }}</dd>
        <dt class="col-5">{% trans "Łączna cena" %}</dt><dd class="col-7">{{ booking.total_price }} zł</dd>
        <dt class="col-5">{% trans "Status" %}</dt>
        <dd class="col-7"><span class="badge {% if booking.status == 'PENDING' %}<form method="post" action="{% url 'booking:checkout' pk=booking.pk %}" class="mt-3">{% csrf_token %}<button type="submit" class="btn btn-success">{% trans "Zapłać" %}</button></form>{% endif %}">{{ booking.get_status_display }}</span></dd>
      </dl>
    </div>
  </div>

  <a href="{% url 'cinema:movie_list' %}" class="btn btn-outline-light mt-4">← {% trans "Repertuar" %}</a>
</article>
{% endblock %}
```

---

### Task 5: Mark Python + email templates

**Files:**
- Modify: `apps/booking/views.py`, `apps/cinema/forms.py`, `apps/booking/services.py`, `apps/booking/forms.py`
- Modify: `templates/accounts/emails/activation_{subject,body}.txt`

- [ ] **Step 1 [User]: `apps/booking/views.py` — wrap 6 messages**

Add the import near the top (with the other `django` imports):
```python
from django.utils.translation import gettext_lazy as _
```
Wrap each message string:
```python
            messages.error(
                request,
                _("Płatność jest chwilowo niedostępna — spróbuj ponownie z poziomu rezerwacji."),
            )
```
```python
            messages.info(request, _("Płatność przyjęta — potwierdzenie rezerwacji wkrótce."))
```
```python
            messages.warning(request, _("Płatność anulowana. Możesz spróbować ponownie."))
```
```python
            messages.success(request, _("Rezerwacja została anulowana."))
```
```python
            messages.error(request, _("Tej rezerwacji nie można już opłacić."))
```
```python
            messages.error(request, _("Płatność jest chwilowo niedostępna — spróbuj ponownie."))
```

- [ ] **Step 2 [User]: `apps/cinema/forms.py` — wrap placeholders + empty_label**

Add import at top:
```python
from django.utils.translation import gettext_lazy as _
```
Change the widget/empty_label literals:
```python
        widget=forms.TextInput(attrs={"placeholder": _("Tytuł filmu..."), "class": "form-control"}),
```
```python
        empty_label=_("Wszystkie gatunki"),
```

- [ ] **Step 3 [User]: `apps/booking/forms.py` — re-key the availability error to shared ngettext**

Add `ngettext` to the existing translation import:
```python
from django.utils.translation import gettext_lazy as _, ngettext
```
Replace the `clean_seats_count` `ValidationError` block:
```python
        if seats_count > available:
            raise forms.ValidationError(
                ngettext(
                    "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę.",
                    "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę.",
                    available,
                ),
                code="exceeds_available",
                params={"count": available},
            )
```
(The other `forms.py` strings — `label`, the four `error_messages`, and the `screening_in_past` `ValidationError` — stay as they are; they're already wrapped and just gain EN `msgstr`s in Task 6.)

- [ ] **Step 4 [User]: `apps/booking/services.py` — wrap the 5 BookingError messages**

Add import at the top (after the existing imports):
```python
from django.utils.translation import gettext as _, ngettext
```
`NotEnoughSeatsError.__init__` (shares the msgid pair with `forms.py`):
```python
    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__(
            ngettext(
                "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę.",
                "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę.",
                available,
            )
            % {"count": available}
        )
```
`ScreeningInPastError.__init__`:
```python
        super().__init__(_("Seans już się rozpoczął — nie można zarezerwować miejsc."))
```
`BookingNotCancellableError.__init__`:
```python
        super().__init__(_("Tej rezerwacji nie można już anulować."))
```
`RefundError.__init__`:
```python
        super().__init__(
            _("Anulowanie nieudane — zwrot płatności nie powiódł się. Skontaktuj się z obsługą.")
        )
```
`BookingNotRefundableError.__init__`:
```python
        super().__init__(_("Tej rezerwacji nie można zwrócić."))
```

> `gettext` (eager), not `gettext_lazy`: these exceptions are instantiated when raised mid-request, so the active request language is correct, and `str(exc)` in the view stays a plain `str`.

- [ ] **Step 5 [User]: `templates/accounts/emails/activation_subject.txt`**

```
{% load i18n %}{% trans "Aktywuj swoje konto KinoMania" %}
```
(`emails.py` already `.strip()`s the rendered subject.)

- [ ] **Step 6 [User]: `templates/accounts/emails/activation_body.txt`**

```
{% load i18n %}{% blocktrans %}Cześć!

Aby aktywować swoje konto KinoMania, kliknij w poniższy link:

{{ activation_url }}

Link jest ważny przez 3 dni. Jeśli to nie Ty zakładałeś konto,
zignoruj tę wiadomość — bez kliknięcia konto pozostanie nieaktywne.

— zespół KinoMania{% endblocktrans %}
```

> `existing tests/accounts/test_emails*` assert the email body/subject content. After this change the **default** (Polish) render differs from the old English text. Claude updates those assertions in Task 6 Step 5 if they break — flag any failure there.

---

### Task 6: Generate, translate, compile, go green

**Files:**
- Modify: `locale/en/LC_MESSAGES/django.{po,mo}`, `locale/pl/LC_MESSAGES/django.{po,mo}`

- [ ] **Step 1 [User]: Verify gettext tools on PATH**

Run: `which xgettext msgfmt msguniq`
Expected: all resolve (US-37 installed mlocati gettext-iconv at `/c/Program Files/gettext-iconv/bin/`). If not, fix PATH before continuing (dev pitfall #25).

- [ ] **Step 2 [User]: makemessages**

Run: `poetry run python manage.py makemessages -l en -l pl --no-wrap --ignore=.venv`
Expected: `locale/en/LC_MESSAGES/django.po` and `locale/pl/LC_MESSAGES/django.po` updated with all new msgids (and `msgid_plural` for the two plural strings). `--no-wrap` keeps long msgids on single lines.

- [ ] **Step 3 [User]: Translate the `en` catalog**

In `locale/en/LC_MESSAGES/django.po`, set each `msgstr` from this table (US-37's navbar entries already filled — leave them). For the two plural entries, fill `msgstr[0]` and `msgstr[1]`; ensure the header reads `"Plural-Forms: nplurals=2; plural=(n != 1);\n"`.

**base.html**
```
"Przełącz nawigację"        -> "Toggle navigation"
"Zamknij"                   -> "Close"
"projekt edukacyjny"        -> "educational project"
```
**accounts**
```
"Logowanie"                                  -> "Sign in"
"Zaloguj się, żeby zarezerwować bilety"      -> "Sign in to book tickets"
"Zaloguj się"                                -> "Sign in"
"Nie dostałeś emaila aktywacyjnego?"         -> "Didn't get the activation email?"
"Nie masz konta?"                            -> "No account?"
"Zarejestruj się"                            -> "Sign up"
"Rejestracja"                                -> "Sign up"
"Stwórz konto i zacznij rezerwować"          -> "Create an account and start booking"
"Po wysłaniu formularza otrzymasz email z linkiem aktywacyjnym." -> "After submitting the form you will receive an email with an activation link."
"Masz już konto?"                            -> "Already have an account?"
"Wyślij ponownie link"                       -> "Resend link"
"Wyślij ponownie link aktywacyjny"           -> "Resend activation link"
"Wyślij ponownie"                            -> "Resend"
"Wpisz email użyty przy rejestracji — jeśli konto czeka na aktywację, wyślemy nowy link." -> "Enter the email you registered with — if the account is awaiting activation, we will send a new link."
"Wyślij"                                     -> "Send"
"Wysłane"                                    -> "Sent"
"Jeśli konto o podanym adresie email istnieje i nie zostało jeszcze aktywowane, wysłaliśmy nowy link aktywacyjny." -> "If an account with the given email exists and has not been activated yet, we have sent a new activation link."
"Link jest ważny przez 3 dni."              -> "The link is valid for 3 days."
"Sprawdź skrzynkę"                           -> "Check your inbox"
"Email wysłany"                              -> "Email sent"
"Wysłaliśmy link aktywacyjny na podany adres. Kliknij w niego, aby aktywować konto." -> "We have sent an activation link to the given address. Click it to activate your account."
"Link jest ważny przez 3 dni. Nie widzisz emaila? Sprawdź folder spam." -> "The link is valid for 3 days. Don't see the email? Check your spam folder."
"Wyślij link ponownie"                       -> "Resend the link"
"Link nieprawidłowy"                         -> "Invalid link"
"Link nieprawidłowy lub wygasł"              -> "Invalid or expired link"
"Link aktywacyjny jest nieprawidłowy lub wygasł." -> "The activation link is invalid or has expired."
"Możliwe przyczyny: link został już użyty, hasło zostało w międzyczasie zmienione, albo link jest starszy niż 3 dni." -> "Possible reasons: the link was already used, the password was changed in the meantime, or the link is older than 3 days."
```
**accounts emails**
```
"Aktywuj swoje konto KinoMania"             -> "Activate your KinoMania account"
(body blocktrans, msgid begins "Cześć!\n\nAby aktywować…")
  -> "Hello!

To activate your KinoMania account, click the link below:

%(activation_url)s

This link is valid for 3 days. If you did not create an account,
just ignore this message — without clicking, the account will
remain inactive.

— the KinoMania team"
```
**accounts (views.py flash messages — already wrapped, need EN)**
```
"Konto jest już aktywne. Możesz się zalogować." -> "Your account is already active. You can sign in."
"Konto aktywowane. Zaloguj się."             -> "Account activated. Sign in."
```
**cinema**
```
"Wszystkie filmy z zaplanowanymi seansami"   -> "All films with scheduled screenings"
"Szukaj"                                     -> "Search"
"Gatunek"                                    -> "Genre"
"Data"                                       -> "Date"
"Filtruj"                                    -> "Filter"
"Wyczyść filtry"                             -> "Clear filters"
"Paginacja"                                  -> "Pagination"
"Poprzednia strona"                          -> "Previous page"
"Następna strona"                            -> "Next page"
"Brak filmów pasujących do wybranych kryteriów." -> "No films match the selected criteria."
"<a href=\"%(ml_url)s\">Wyczyść filtry</a> żeby zobaczyć wszystkie." -> "<a href=\"%(ml_url)s\">Clear filters</a> to see all films."
"Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!" -> "No films with scheduled screenings right now. Check back soon!"
"Tytuł filmu..."                             -> "Film title..."
"Wszystkie gatunki"                          -> "All genres"
"Premiera %(d)s"                             -> "Premiere %(d)s"
"Reż."                                       -> "Dir."
"Obsada:"                                    -> "Cast:"
"i inni"                                     -> "and others"
"Zwiastun"                                   -> "Trailer"
"Zwiastun: %(t)s"                            -> "Trailer: %(t)s"
"Zobacz zwiastun (link zewnętrzny)"          -> "Watch trailer (external link)"
"Reżyseria"                                  -> "Directors"
"Obsada"                                     -> "Cast"
"Poprzedni"                                  -> "Previous"
"Następny"                                   -> "Next"
"Nadchodzące seanse"                         -> "Upcoming screenings"
"Sala %(name)s"                              -> "Hall %(name)s"
"Brak zaplanowanych seansów dla tego filmu." -> "No scheduled screenings for this film."
"Pokaż"                                      -> "Show"
"Wróć do dzisiejszego dnia"                  -> "Back to today"
"Dzisiaj"                                    -> "Today"
"Brak seansów na dzień %(d)s."               -> "No screenings on %(d)s."
```
**booking (templates)**
```
"Nadchodzące"                                -> "Upcoming"
"Historia"                                   -> "History"
"Anuluj"                                     -> "Cancel"
"Brak historycznych rezerwacji."            -> "No past bookings."
"Nie masz nadchodzących rezerwacji. <a href=\"%(ml_url)s\">Przeglądaj repertuar</a>." -> "You have no upcoming bookings. <a href=\"%(ml_url)s\">Browse the program</a>."
"Rezerwacja"                                 -> "Booking"
"Termin"                                     -> "Date and time"
"Sala"                                       -> "Hall"
"Cena za miejsce"                            -> "Price per seat"
"Dostępne miejsca"                           -> "Available seats"
"Razem:"                                     -> "Total:"
"Zarezerwuj i zapłać"                        -> "Book and pay"
"Rezerwacja #%(id)s"                         -> "Booking #%(id)s"
"Liczba miejsc"                              -> "Number of seats"
"Łączna cena"                                -> "Total price"
"Status"                                     -> "Status"
"Zapłać"                                     -> "Pay"
```
**booking (plural — seat count display, `msgid_plural`)**
```
msgid        "%(counter)s miejsce"
msgid_plural "%(counter)s miejsc"
msgstr[0]    "%(counter)s seat"
msgstr[1]    "%(counter)s seats"
```
**booking models / forms / services / views (Python)**
```
"Oczekująca"                                 -> "Pending"
"Potwierdzona"                               -> "Confirmed"
"Anulowana"                                  -> "Cancelled"
"Podaj liczbę miejsc."                       -> "Enter the number of seats."
"Podaj poprawną liczbę miejsc."             -> "Enter a valid number of seats."
"Musisz zarezerwować co najmniej 1 miejsce." -> "You must book at least 1 seat."
"Maksymalnie możesz zarezerwować 10 miejsc." -> "You can book at most 10 seats."
"Seans już się rozpoczął — nie można zarezerwować miejsc." -> "The screening has already started — seats can no longer be booked."
"Tej rezerwacji nie można już anulować."    -> "This booking can no longer be cancelled."
"Anulowanie nieudane — zwrot płatności nie powiódł się. Skontaktuj się z obsługą." -> "Cancellation failed — the refund did not go through. Please contact support."
"Tej rezerwacji nie można zwrócić."          -> "This booking cannot be refunded."
"Płatność jest chwilowo niedostępna — spróbuj ponownie z poziomu rezerwacji." -> "Payment is temporarily unavailable — try again from the booking."
"Płatność przyjęta — potwierdzenie rezerwacji wkrótce." -> "Payment received — booking confirmation coming soon."
"Płatność anulowana. Możesz spróbować ponownie." -> "Payment cancelled. You can try again."
"Rezerwacja została anulowana."             -> "The booking has been cancelled."
"Tej rezerwacji nie można już opłacić."     -> "This booking can no longer be paid for."
"Płatność jest chwilowo niedostępna — spróbuj ponownie." -> "Payment is temporarily unavailable — try again."
```
**booking (plural — availability error, `msgid_plural`)**
```
msgid        "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę."
msgid_plural "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę."
msgstr[0]    "Only %(count)d seat is available — choose a smaller number."
msgstr[1]    "Only %(count)d seats are available — choose a smaller number."
```
**English-source model labels (out of scope to *translate*, but `makemessages` extracts them).**
Every remaining entry whose `msgid` is already English — the `apps/cinema/models.py` /
`apps/booking/models.py` field labels and `verbose_name`s (`seats count`, `status`, `name`,
`genre`, `actor`, `director`, `photo`, `biography`, `description`, `capacity`, `Stripe session
ID`, `Stripe payment intent ID`, `refund ID`, `refunded at`, `created at`, `expires at`, `user`,
`screening`, `booking`, `bookings`, `genres`, `actors`, `directors`, …) — set `msgstr` to the
**same English text** (copy msgid → msgstr). This leaves admin behavior unchanged (`pl` stays
empty → English fallback, as today) but keeps the en catalog fully filled so the
`test_en_catalog_has_no_empty_msgstr` gate is unambiguous: an empty en `msgstr` then always means
a genuinely forgotten string.

- [ ] **Step 4 [User]: Fill the `pl` plural forms**

In `locale/pl/LC_MESSAGES/django.po`, **leave singular `msgstr`s empty** (Polish msgid is the source). Set the header to Polish 3-form:
```
"Plural-Forms: nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);\n"
```
Fill the two plural entries with all three Polish forms:
```
msgid        "%(counter)s miejsce"
msgid_plural "%(counter)s miejsc"
msgstr[0]    "%(counter)s miejsce"
msgstr[1]    "%(counter)s miejsca"
msgstr[2]    "%(counter)s miejsc"
```
```
msgid        "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę."
msgid_plural "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę."
msgstr[0]    "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę."
msgstr[1]    "Dostępnych jest tylko %(count)d miejsca — wybierz mniejszą liczbę."
msgstr[2]    "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę."
```
De-fuzz any entry `makemessages` flagged `#, fuzzy` (remove the flag once the `msgstr` is correct); delete obsolete `#~` lines.

- [ ] **Step 5 [User]: compilemessages, then run i18n tests**

Run: `poetry run python manage.py compilemessages`
Expected: rewrites both `django.mo`.

Run: `poetry run pytest tests/test_i18n.py -q --no-cov`
Expected: PASS (7 passed — 4 from US-37 + 3 new).

If `tests/accounts/test_emails*` (or any test asserting the activation email text) breaks because the default render is now Polish: **[Claude]** updates those assertions to the Polish source (or wraps them in `translation.override("en")` if they intend to check English). Re-run that test module to green.

- [ ] **Step 6 [User]: Commit**

```bash
git add templates/ apps/booking/views.py apps/booking/services.py apps/booking/forms.py apps/cinema/forms.py locale/ tests/test_i18n.py .Claude/backlog.md
git commit -m "feat(FR-15): translate all user-facing strings PL/EN (US-38)"
```
(The spec + plan are committed separately up front as `docs(M5): US-38 translations spec + plan`, matching the US-37 flow.)

---

### Task 7: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%. Watch the auth-template regression test
(`tests/cinema/test_accounts_templates_regression.py`) and any email-content test — they assert
rendered text; if they checked Polish literals that are now `{% trans %}`-wrapped, the default
(pl) render is unchanged, so they should stay green. Any failure → **[Claude]** adjusts the test.

- [ ] **Step 2 [User]: Lint + format + type-check**

Run: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .`
Expected: clean. Note `gettext as _, ngettext` is used in `services.py`; `gettext_lazy as _, ngettext` in `forms.py`; `locale/` is ruff-excluded.

- [ ] **Step 3 [User]: Manual smoke (optional)**

`runserver` → browse catalog/screenings/a booking in PL; switch to EN via the navbar →
headings, filters, buttons, badges, flash messages, and the activation email all render English;
seat counts read "1 seat / 2 seats"; switch back → Polish "1 miejsce / 2 miejsca / 5 miejsc".

---

## Status board update

In `.Claude/backlog.md` §7, move US-38 to **In Progress (WIP=1)** when starting, and to **Done**
after merge (handled in the commit of Task 6 / on PR merge).

## Out of scope

Django admin model labels (incl. unwrapped `apps/accounts/models.py`) · DRF API messages ·
error pages (US-39) · `i18n_patterns` on URLs · per-user stored language preference.

## Test plan summary

- `tests/test_i18n.py` (extends US-37's 4): **en-coverage gate** (no empty/fuzzy `msgstr`),
  **plural** (EN 2-form + PL 3-form seat counts), **page smoke** (catalog page renders US-38
  English after switching). 7 tests total.
- Existing suite unaffected at the **default** (Polish) language; any email-text test that breaks
  is realigned by Claude.
- Coverage ≥ 80% (string-wrapping adds no branches); no migration.
