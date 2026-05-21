# KinoMania — redesign w stylu Cinema City

**Data:** 2026-05-21
**Branch (kontekst):** `feat/FR-04-screening-list`
**Powiązane:** `.Claude/tooling_stack.md`, obecne `templates/base.html`, `templates/cinema/*.html`

---

## 1. Cel

Zmiana wizualna aplikacji KinoMania tak, by przypominała stylistycznie [cinema-city.pl](https://www.cinema-city.pl/#/): ciemny motyw, plakaty filmów dominują, pigułki godzin zamiast tabel seansów. **Bez zmian backendu, bez nowych ficzerów.** Wszystkie obecne dane i widoki działają jak teraz — zmieniamy tylko CSS i strukturę HTML.

### Out of scope
- Nowe pola w modelach (np. `age_rating`)
- Nowe sekcje na stronach (hero carousel, „Wkrótce w kinie")
- Redesign template'ów `accounts/*` (dziedziczą base.html → dostają nowe kolory/fonty automatycznie)
- Zmiany w views, urls, models, settings (poza wpięciem statics jeśli brakuje)

---

## 2. Architektura plików

### Nowe pliki

```
static/
└── css/
    ├── theme.css          # CSS variables + override Bootstrap (paleta, typografia)
    └── components.css     # własne komponenty: pigułki, karty filmów, hero
```

### Edytowane

```
templates/
├── base.html                       # nav (sticky), footer, ładowanie theme.css + components.css + Inter
└── cinema/
    ├── movie_list.html             # grid kart "movie wall" (poster + overlay)
    ├── screening_list.html         # pigułki godzin grupowane po sali
    └── movie_detail.html           # hero + zwiastun + reżyseria + obsada + pigułki dat
```

### Stan obecny — zweryfikowane

| Element | Stan |
|---------|------|
| `static/` na poziomie repo | ❌ nie istnieje — utworzymy |
| `STATIC_URL = "static/"` w `settings/base.py:88` | ✅ jest |
| `STATICFILES_DIRS` w `settings/base.py` | ❌ NIE JEST — trzeba dodać: `STATICFILES_DIRS = [BASE_DIR / "static"]` |
| `{% load static %}` w `base.html:1` | ✅ jest |
| `django.template.context_processors.request` w settings TEMPLATES | ✅ jest (linia 54) — `request.resolver_match` zadziała w nav |

---

## 3. Design tokens (`static/css/theme.css`)

```css
:root {
  /* Paleta */
  --bg: #0f1115;
  --bg-elev: #181a20;
  --border: #2a2d34;
  --text: #ffffff;
  --text-muted: #b3b6bf;

  --accent: #8B5CF6;
  --accent-hover: #7C3AED;
  --accent-bg: rgba(139, 92, 246, 0.15);

  --success: #10b981;
  --danger: #ef4444;

  /* Spacing (skala 4px) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-5: 20px; --space-6: 24px;
  --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* Radius */
  --radius-sm: 4px;   /* pigułka, badge */
  --radius-md: 6px;   /* karta */
  --radius-lg: 12px;  /* hero, modal */
}

/* Bootstrap override */
:root {
  --bs-body-bg: var(--bg);
  --bs-body-color: var(--text);
  --bs-primary: var(--accent);
  --bs-primary-rgb: 139, 92, 246;
  --bs-tertiary-bg: var(--bg-elev);
  --bs-border-color: var(--border);
  --bs-link-color: var(--accent);
  --bs-link-hover-color: var(--accent-hover);
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
}

/* Active nav link */
.navbar .nav-link.active {
  border-bottom: 2px solid var(--accent);
  padding-bottom: calc(0.5rem - 2px);
}
@media (max-width: 991.98px) {
  .navbar .nav-link.active {
    border-bottom: 0;
    border-left: 3px solid var(--accent);
    padding-left: calc(1rem - 3px);
  }
}
```

### Typografia

Inter z Google Fonts. W `base.html` w `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
```

Wagi: 400 (body), 600 (button/link), 700 (h2/h3), 800 (h1).
Skala: h1 32px / 800 / `letter-spacing: -0.02em`; h2 22px / 700; h3 18px / 700; body 14px / 400 / `line-height: 1.6`; label 11px / 600 / uppercase / `letter-spacing: 1px`.

---

## 4. Komponenty (`static/css/components.css`)

### 4.1. Time-pill (pigułka godziny)

```css
.time-pill {
  display: inline-block;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 13px;
  text-decoration: none;
  transition: border-color 0.15s, background 0.15s;
}
.time-pill:hover { border-color: var(--accent); background: var(--accent-bg); color: var(--text); }
.time-pill.is-soldout {
  opacity: 0.5;
  text-decoration: line-through;
  pointer-events: none;
}
.time-pill-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.time-pill-hall-label {
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin-bottom: 6px;
}
```

**Stan sold-out** — klasa `is-soldout` dodawana gdy `screening.available_seats_count == 0`. Obecnie `booked_seats_count()` zwraca zawsze 0 (TODO w modelu, do US-18), więc klasa nigdy nie jest renderowana — ale CSS jest gotowy.

### 4.2. Movie-card (wariant C, „movie wall")

```css
.movie-card {
  position: relative;
  aspect-ratio: 2/3;
  background: linear-gradient(135deg, #4a4d54 0%, #2a2d34 100%);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s;
}
.movie-card:hover { transform: translateY(-2px); }
.movie-card__img { width: 100%; height: 100%; object-fit: cover; display: block; }
.movie-card__placeholder { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 48px; opacity: 0.6; }
.movie-card__overlay {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  padding: 14px 12px 10px;
  background: linear-gradient(180deg, transparent, rgba(0,0,0,0.92));
}
.movie-card__title { color: var(--text); font-weight: 700; font-size: 13px; line-height: 1.2; }
.movie-card__meta { color: var(--text-muted); font-size: 10px; margin-top: 3px; }
```

Grid kontener (Bootstrap):
```html
<div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-xl-5 g-3">
```

### 4.3. Screening-card (karta filmu na liście seansów)

```css
.screening-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-bottom: 16px;
  display: flex;
  gap: 18px;
}
.screening-card__poster { width: 90px; flex-shrink: 0; aspect-ratio: 2/3; border-radius: 4px; overflow: hidden; }
.screening-card__body { flex: 1; min-width: 0; }
.screening-card__title { color: var(--text); font-weight: 700; font-size: 18px; text-decoration: none; }
.screening-card__title:hover { color: var(--accent); }
.screening-card__meta { color: var(--text-muted); font-size: 12px; margin-top: 4px; }

/* Per-day block na movie_detail (bez plakatu) */
.screening-day {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px;
  margin-bottom: 12px;
}
.screening-day__date {
  color: var(--text);
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 14px;
}
```

### 4.4. Hero (movie_detail)

```css
.movie-hero { position: relative; padding: 48px 0; overflow: hidden; }
.movie-hero__bg {
  position: absolute; inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(40px);
  opacity: 0.4;
  transform: scale(1.2);
  z-index: 0;
}
.movie-hero__bg::after {
  content: '';
  position: absolute; inset: 0;
  background: rgba(15, 17, 21, 0.7);
}
.movie-hero__inner { position: relative; z-index: 1; display: flex; gap: 32px; }
.movie-hero__poster { width: 220px; flex-shrink: 0; aspect-ratio: 2/3; border-radius: 8px; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,0.5); }
.movie-hero__title { color: var(--text); font-size: 36px; font-weight: 800; letter-spacing: -0.02em; margin: 8px 0 4px; }
.movie-hero__meta { color: var(--text-muted); font-size: 14px; margin-bottom: 14px; }
.movie-hero__genre-badge {
  background: var(--accent-bg);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
}
.movie-hero__description { color: var(--text); font-size: 14px; line-height: 1.7; max-width: 680px; }
```

### 4.5. Filter-bar

```css
.filter-bar {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  margin-bottom: 24px;
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.filter-bar input,
.filter-bar select {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  width: 100%;     /* fill flex parent */
}
.filter-bar > div { display: flex; flex-direction: column; }
.filter-bar label {
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  display: block;
}
```

---

## 5. base.html — struktura

```html
{% load static %}
<!DOCTYPE html>
<html lang="pl" data-bs-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}KinoMania{% endblock %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{% static 'css/theme.css' %}" rel="stylesheet">
    <link href="{% static 'css/components.css' %}" rel="stylesheet">
</head>
<body class="d-flex flex-column min-vh-100">

<nav class="navbar navbar-expand-lg sticky-top" style="background: var(--bg-elev); border-bottom: 1px solid var(--border);">
    <div class="container">
        <a class="navbar-brand fw-bold" href="/">
            <span style="color: var(--accent);">🎬</span> KinoMania
        </a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navMain">
            {# `home` i `movie_list` to aliasy tej samej view; `movie_detail` traktujemy jako child sekcji Repertuar #}
            <ul class="navbar-nav me-auto">
                <li class="nav-item">
                    <a class="nav-link {% if request.resolver_match.url_name == 'home' or request.resolver_match.url_name == 'movie_list' or request.resolver_match.url_name == 'movie_detail' %}active{% endif %}"
                       href="{% url 'cinema:home' %}">Repertuar</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link {% if request.resolver_match.url_name == 'screening_list' %}active{% endif %}"
                       href="{% url 'cinema:screening_list' %}">Seanse</a>
                </li>
            </ul>
            <ul class="navbar-nav align-items-lg-center">
                {% if user.is_authenticated %}
                <li class="nav-item me-lg-3"><span class="navbar-text text-muted small">{{ user.email }}</span></li>
                <li class="nav-item">
                    <form method="post" action="{% url 'accounts:logout' %}" class="d-inline">
                        {% csrf_token %}
                        <button type="submit" class="btn btn-outline-light btn-sm">Wyloguj</button>
                    </form>
                </li>
                {% else %}
                <li class="nav-item"><a class="nav-link" href="{% url 'accounts:login' %}">Zaloguj</a></li>
                <li class="nav-item">
                    <a class="btn btn-primary btn-sm ms-lg-2" href="{% url 'accounts:register' %}">Zarejestruj</a>
                </li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>

<main class="container py-4 flex-grow-1">
    {% if messages %}
    {% for message in messages %}
    <div class="alert alert-{{ message.tags|default:'info' }} alert-dismissible fade show" role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
    {% endfor %}
    {% endif %}
    {% block content %}{% endblock %}
</main>

<footer class="py-3 mt-auto" style="background: var(--bg-elev); border-top: 1px solid var(--border);">
    <div class="container d-flex justify-content-between align-items-center small text-muted">
        <span><span style="color: var(--accent);">🎬</span> <strong style="color: var(--text);">KinoMania</strong> · © 2026 · projekt edukacyjny</span>
        <span>Powered by Django</span>
    </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

### Decyzje base.html

- **`data-bs-theme="dark"`** — Bootstrap 5.3 dark mode tokens
- **`sticky-top`** na nav
- **Aktywny link**: `.active` w klasie `.nav-link` + CSS w theme.css doda dolny border 2px w `--accent`:
  ```css
  .navbar .nav-link.active {
    border-bottom: 2px solid var(--accent);
    padding-bottom: calc(0.5rem - 2px);
  }
  ```
- **Logo emoji** ma kolor akcentu (inline style — pojedyncze użycie, nie tworzymy klasy)
- **„Zarejestruj" jako solid CTA**, „Zaloguj" jako zwykły link, „Wyloguj" jako `btn-outline-light`

---

## 6. movie_list.html — szczegóły

```django
{% extends "base.html" %}
{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1" style="font-size:32px; font-weight:800; letter-spacing:-0.02em;">Repertuar</h1>
<p class="text-muted small mb-4">Wszystkie filmy z zaplanowanymi seansami</p>

<form method="get" class="filter-bar" role="search">
    <div style="flex:2;">{{ filter_form.q }}</div>
    <div style="flex:1;">{{ filter_form.genre }}</div>
    <div style="flex:1;">{{ filter_form.date }}</div>
    <button type="submit" class="btn btn-primary">Filtruj</button>
    {% if request.GET %}
    <a href="{% url 'cinema:movie_list' %}" class="btn btn-outline-light" title="Wyczyść">×</a>
    {% endif %}
</form>

{% if movies %}
<div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-xl-5 g-3">
    {% for movie in movies %}
    <div class="col">
        <a href="{{ movie.get_absolute_url }}" class="movie-card d-block text-decoration-none">
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
<nav aria-label="Paginacja" class="mt-4">
    <ul class="pagination justify-content-center">
        {% if page_obj.has_previous %}
        <li class="page-item"><a class="page-link" href="?{% querystring page=page_obj.previous_page_number %}">«</a></li>
        {% endif %}
        <li class="page-item active"><span class="page-link">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span></li>
        {% if page_obj.has_next %}
        <li class="page-item"><a class="page-link" href="?{% querystring page=page_obj.next_page_number %}">»</a></li>
        {% endif %}
    </ul>
</nav>
{% endif %}
{% else %}
<div class="alert alert-info">
    {% if request.GET %}
    Brak filmów pasujących do wybranych kryteriów. <a href="{% url 'cinema:movie_list' %}">Wyczyść filtry</a>.
    {% else %}
    Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

### Decyzje movie_list

- **„Najbliższy seans" znika z karty** (wariant C, plakat z overlayem). `next_screening_at` zostaje w queryset bo jest używany do sortowania.
- **Klik w cały plakat** prowadzi do `movie_detail` (cała karta to `<a>`).
- **Filtry**: te same widgety co teraz (`q`, `genre`, `date`), tylko w nowym pudełku `.filter-bar`.

---

## 7. screening_list.html — szczegóły

```django
{% extends "base.html" %}
{% load static %}

{% block title %}Seanse — {{ effective_date|date:"d.m.Y" }} — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1" style="font-size:32px; font-weight:800; letter-spacing:-0.02em;">Seanse</h1>
<p class="text-muted small mb-4">{{ effective_date|date:"l, j E Y" }}</p>

<form method="get" class="filter-bar" role="search">
    <div>
        <label for="date-input">Data</label>
        <input type="date" id="date-input" name="date"
               min="{{ today|date:'Y-m-d' }}"
               max="{{ max_date|date:'Y-m-d' }}"
               value="{{ effective_date|date:'Y-m-d' }}">
    </div>
    <button type="submit" class="btn btn-primary">Pokaż</button>
    {% if request.GET.date %}
    <a href="{% url 'cinema:screening_list' %}" class="btn btn-outline-light">Dzisiaj</a>
    {% endif %}
</form>

{% if movie_groups %}
{% for movie, screenings in movie_groups %}
<div class="screening-card">
    <div class="screening-card__poster">
        {% if movie.poster %}
        <img src="{{ movie.poster.url }}" alt="{{ movie.title }}" style="width:100%; height:100%; object-fit:cover;">
        {% else %}
        <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; font-size:28px; background:linear-gradient(135deg,#4a4d54,#2a2d34);" aria-hidden="true">🎬</div>
        {% endif %}
    </div>
    <div class="screening-card__body">
        <a href="{{ movie.get_absolute_url }}" class="screening-card__title">{{ movie.title }}</a>
        <div class="screening-card__meta">
            {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %} · {% endif %}{% endfor %}
            · {{ movie.duration_minutes }} min
        </div>

        {# regroup wymaga posortowanego inputu po grouperze; sortujemy po hall.name, w obrębie sali zachowujemy start_time ASC (już z Meta.ordering Screening) #}
        {% regroup screenings|dictsort:"hall.name" by hall.name as hall_groups %}
        {% for hall_group in hall_groups %}
        <div class="mt-3">
            <div class="time-pill-hall-label">Sala {{ hall_group.grouper }}</div>
            <div class="time-pill-group">
                {% for s in hall_group.list %}
                <a href="#" class="time-pill {% if not s.is_available %}is-soldout{% endif %}">{{ s.start_time|date:"H:i" }}</a>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endfor %}
{% else %}
<div class="alert alert-info">
    Brak seansów na dzień {{ effective_date|date:"d.m.Y" }}.
</div>
{% endif %}
{% endblock %}
```

### Decyzje screening_list

- **`{% regroup screenings|dictsort:"hall.name" by hall.name as hall_groups %}`** w template — `dictsort` przed regroup jest kluczowy, bo screenings są domyślnie posortowane po `start_time` ASC (Meta.ordering w modelu Screening), a regroup zaczyna nową grupę przy każdej zmianie wartości grouper. Bez `dictsort` salame mogłyby się powielić w wyniku.
- **Pigułki neutralne**, akcent dopiero na hover (klasa `.time-pill` bez modyfikatora).
- **Sold-out** przez `is-soldout` (CSS gotowy, dziś nigdy nie zadziała — `booked_seats_count` to TODO).
- **Pigułki linkują do `#`** (placeholder). Realny link do `screening_detail` przyjdzie w przyszłej historyjce.

---

## 8. movie_detail.html — szczegóły

Trzymamy obecne sekcje (zwiastun, reżyseria, obsada-carousel) i nakładamy nowy theme. Sekcja seansów (dotychczas tabela) → konwertujemy na pigułki grupowane po dacie.

```django
{% extends "base.html" %}

{% block title %}{{ movie.title }} — KinoMania{% endblock %}

{% block content %}
<article>
    <a href="{% url 'cinema:movie_list' %}" class="text-muted small text-decoration-none">← Repertuar</a>

    <div class="movie-hero">
        {% if movie.poster %}
        <div class="movie-hero__bg" style="background-image: url('{{ movie.poster.url }}');"></div>
        {% endif %}
        <div class="movie-hero__inner">
            <div class="movie-hero__poster">
                {% if movie.poster %}
                <img src="{{ movie.poster.url }}" alt="{{ movie.title }}" style="width:100%; height:100%; object-fit:cover;">
                {% else %}
                <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; font-size:64px; background:linear-gradient(135deg,#4a4d54,#2a2d34);" aria-hidden="true">🎬</div>
                {% endif %}
            </div>
            <div style="flex:1;">
                <h1 class="movie-hero__title">{{ movie.title }}</h1>
                <div class="movie-hero__meta">
                    {{ movie.duration_minutes }} min ·
                    {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %}, {% endif %}{% endfor %}
                    {% if movie.directors.all %} · Reż. {% for d in movie.directors.all %}{{ d.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% endif %}
                </div>
                <div class="d-flex gap-2 mb-3">
                    {% for genre in movie.genres.all %}
                    <span class="movie-hero__genre-badge">{{ genre.name }}</span>
                    {% endfor %}
                </div>
                <p class="movie-hero__description">{{ movie.description|linebreaksbr }}</p>
                {% if movie.actors.all %}
                <p class="text-muted small mt-3 mb-0">
                    <strong style="color: var(--text);">Obsada:</strong>
                    {% for a in movie.actors.all|slice:":6" %}{{ a.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}
                </p>
                {% endif %}
            </div>
        </div>
    </div>

    {# Zwiastun #}
    {% if trailer_embed_url %}
    <section class="my-5">
        <h2 class="h4 mb-3">Zwiastun</h2>
        <iframe src="{{ trailer_embed_url }}" title="Zwiastun: {{ movie.title }}"
                width="100%" style="aspect-ratio: 16/9; border-radius: var(--radius-md);"
                frameborder="0"
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                referrerpolicy="strict-origin-when-cross-origin"
                sandbox="allow-scripts allow-same-origin allow-presentation"
                allowfullscreen></iframe>
    </section>
    {% elif movie.trailer_url %}
    <section class="my-5">
        <h2 class="h4 mb-3">Zwiastun</h2>
        <a href="{{ movie.trailer_url }}" class="btn btn-outline-light" target="_blank" rel="noopener noreferrer">Zobacz zwiastun (link zewnętrzny)</a>
    </section>
    {% endif %}

    {# Reżyseria #}
    {% if movie.directors.all %}
    <section class="my-5">
        <h2 class="h4 mb-3">Reżyseria</h2>
        <div class="row row-cols-2 row-cols-md-4 g-3">
            {% for director in movie.directors.all %}
            <div class="col text-center">
                {% if director.photo %}
                <img src="{{ director.photo.url }}" alt="{{ director.full_name }}"
                     class="rounded-circle mb-2"
                     style="width:80px; height:80px; object-fit:cover; border:2px solid var(--border);">
                {% else %}
                <div class="rounded-circle d-flex align-items-center justify-content-center mb-2 mx-auto"
                     style="width:80px; height:80px; font-size:2rem; background:var(--bg-elev); border:2px solid var(--border);" aria-hidden="true">👤</div>
                {% endif %}
                <div class="small">{{ director.full_name }}</div>
            </div>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {# Obsada — Bootstrap Carousel (zachowany, restyled) #}
    {% if movie.actors.all %}
    <section class="my-5">
        <h2 class="h4 mb-3">Obsada</h2>
        <div id="actorsCarousel" class="carousel slide" data-bs-ride="false"
             style="background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-md);">
            <div class="carousel-inner">
                {% for actor in movie.actors.all %}
                <div class="carousel-item {% if forloop.first %}active{% endif %}">
                    <div class="text-center py-4">
                        {% if actor.photo %}
                        <img src="{{ actor.photo.url }}" alt="{{ actor.full_name }}"
                             class="rounded-circle mb-2"
                             style="width:140px; height:140px; object-fit:cover; border:2px solid var(--border);">
                        {% else %}
                        <div class="rounded-circle d-flex align-items-center justify-content-center mb-2 mx-auto"
                             style="width:140px; height:140px; font-size:3rem; background:var(--bg); border:2px solid var(--border);" aria-hidden="true">👤</div>
                        {% endif %}
                        <div>{{ actor.full_name }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            <button class="carousel-control-prev" type="button" data-bs-target="#actorsCarousel" data-bs-slide="prev">
                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                <span class="visually-hidden">Poprzedni</span>
            </button>
            <button class="carousel-control-next" type="button" data-bs-target="#actorsCarousel" data-bs-slide="next">
                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                <span class="visually-hidden">Następny</span>
            </button>
        </div>
    </section>
    {% endif %}

    {# Nadchodzące seanse — pigułki grupowane po dacie i sali #}
    <section class="my-5">
        <h2 class="h4 mb-3">Nadchodzące seanse</h2>
        {% if upcoming_screenings %}
            {# upcoming_screenings z queryset jest posortowane po start_time ASC, więc regroup po dacie działa od razu #}
            {% regroup upcoming_screenings by start_time|date:"Y-m-d" as date_groups %}
            {% for date_group in date_groups %}
            <div class="screening-day">
                <div class="screening-day__date">{{ date_group.list.0.start_time|date:"l, j E" }}</div>
                {# w obrębie dnia musimy posortować po sali przed regroup #}
                {% regroup date_group.list|dictsort:"hall.name" by hall.name as hall_groups %}
                {% for hall_group in hall_groups %}
                <div class="mt-2">
                    <div class="time-pill-hall-label">Sala {{ hall_group.grouper }}</div>
                    <div class="time-pill-group">
                        {% for s in hall_group.list %}
                        <a href="#" class="time-pill {% if not s.is_available %}is-soldout{% endif %}">{{ s.start_time|date:"H:i" }}</a>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        {% else %}
        <div class="alert alert-info">Brak zaplanowanych seansów dla tego filmu.</div>
        {% endif %}
    </section>
</article>
{% endblock %}
```

### Decyzje movie_detail

- **Hero z rozmytym plakatem w tle** — `background-image: url(poster)` + `filter: blur(40px)` + ciemna mgła.
- **Krótka lista obsady w hero** (top 6 nazwisk, `|slice:":6"`) + sekcja Obsada niżej z fotami (duplikacja świadoma — szybki podgląd vs pełna lista).
- **Sekcje opcjonalne** — Zwiastun/Reżyseria/Obsada renderują się tylko gdy są dane (`{% if %}`).
- **Karuzela Obsada** zachowana (Bootstrap Carousel, restyled przez kolory ramek i tła).
- **Sekcja seansów** — `{% regroup %}` najpierw po dacie (`start_time|date:"Y-m-d"`), potem po sali. Pigułki identyczne jak w `screening_list`.
- **Brak age_rating** — pole nie istnieje w modelu, nie renderujemy badge'a.

---

## 9. Responsywność

| Breakpoint | movie_list grid | nav | hero | screening_card |
|------------|-----------------|-----|------|----------------|
| ≥1200px (xl) | 5 col | desktop | row, plakat 220px | row |
| ≥992px (lg) | 4 col | desktop | row, plakat 220px | row |
| ≥768px (md) | 4 col | collapse | row, plakat 180px | row |
| ≥576px (sm) | 3 col | collapse | column, plakat full | row |
| <576px | 2 col | collapse | column, plakat full | column |

Mobile-first przez Bootstrap grid (`row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-xl-5`).

---

## 10. Testowanie

### Co testujemy

Redesign to czysty CSS/HTML — **żadnych nowych testów logiki**. Sprawdzamy tylko, że istniejące testy nadal przechodzą (brak regresji w widokach).

### Testy do uruchomienia po implementacji

```bash
poetry run pytest -x
poetry run ruff check templates/  # nie obowiązuje, ale nie zaszkodzi
```

### Sanity check ręczny

1. `python manage.py runserver` → `localhost:8000/`
2. Strony do przeklikania: `/`, `/seanse`, `/seanse?date=jutro`, `/film/<slug-z-seed>/`, `/accounts/login/`, `/accounts/register/`
3. Sprawdzić: dark theme w accounts (dziedziczy base), responsywność (DevTools mobile), aktywny link w nav, plakat z gradientcie czytelny.
4. Network tab: czy `theme.css`, `components.css`, Inter font ładują się 200.

### Regresja N+1

Test z `81adb77` (`test_screening_list_query_budget_regression`) musi przejść — template `screening_list.html` jest przepisany, ale queryset nie ruszamy. Jeśli `{% regroup %}` ujawni problem (mało prawdopodobne — grupuje już-załadowane dane) → fix w widoku.

---

## 11. Kolejność implementacji (high-level)

1. **Statics setup** — `static/css/` + sprawdzenie `STATICFILES_DIRS`.
2. **`theme.css`** — paleta + override Bootstrap + typografia.
3. **`components.css`** — `.time-pill`, `.movie-card`, `.screening-card`, `.movie-hero`, `.filter-bar`.
4. **`base.html`** — fonts, sticky nav, footer.
5. **`movie_list.html`** — przepisać na movie-card grid.
6. **`screening_list.html`** — przepisać na pigułki + regroup.
7. **`movie_detail.html`** — hero + restyle istniejących sekcji + pigułki dat.
8. **`pytest`** — wszystkie testy zielone.
9. **Ręczna weryfikacja w przeglądarce** — checklist z §10.

---

## 12. Co dostaje a co nie dostaje branch po implementacji

**Dostaje:**
- Nowy globalny look (dark + fiolet + Inter)
- Wszystkie 3 strony cinema w stylu cinema-city.pl
- Sticky nav, hero na movie_detail z rozmytym tłem
- Pigułki godzin zamiast tabel
- Zachowana cała obecna funkcjonalność (filtry, paginacja, obsada-carousel, trailer)

**Nie dostaje:**
- Hero carousel na home
- Age rating badges (brak pola w modelu)
- Nowe ficzery typu „Wkrótce w kinie", „Akcje promocyjne"
- Refactor istniejących widoków/modeli
