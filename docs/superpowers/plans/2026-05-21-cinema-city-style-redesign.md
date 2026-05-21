# KinoMania — Cinema City Style Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przeprojektować wygląd aplikacji KinoMania w stylu cinema-city.pl (dark theme + fioletowy akcent + pigułki godzin + plakaty-dominanty), nie zmieniając logiki backendu ani testów.

**Architecture:** Czysty CSS + HTML. Dodajemy dwa pliki statyczne (`theme.css` — design tokens i Bootstrap override; `components.css` — komponenty: pigułki, karty filmów, hero) i przepisujemy 4 templatki (`base.html` + 3 strony cinema). Żadnych zmian w `models.py`, `views.py`, `urls.py`, `forms.py`.

**Tech Stack:** Django 6 + Bootstrap 5.3.3 (CDN, zostaje) + custom CSS override + Inter (Google Fonts).

**Spec źródłowy:** `docs/superpowers/specs/2026-05-21-cinema-city-style-redesign.md` — jeśli plan jest niejasny, sięgnij do speca.

**Założenie testowe:** Redesign nie tworzy nowych jednostkowych testów logiki (nie ma logiki do testowania). Każdy task kończy się: (1) pełnym `pytest -x` (brak regresji), (2) wizualnym smoke check w przeglądarce, (3) propozycją commit message. Test regresji N+1 (`test_screening_list_query_budget_regression` z `81adb77`) musi pozostać zielony.

**Role division (per `.Claude/commit_convention.md` §10):**
- Claude podaje **pełną zawartość** plików (CSS/HTML) w blokach.
- User **kopiuje** zawartość do plików w IDE.
- User uruchamia wszystkie komendy (`pytest`, `runserver`, `git`).
- Claude weryfikuje wynik i proponuje commit message.

---

## Branch Strategy (do uzgodnienia przed Task 1)

Obecny branch: `feat/FR-04-screening-list`. Redesign nie jest częścią FR-04. Rekomendacja:

```bash
# 1. Upewnij się że FR-04 jest pushnięte i PR-ed osobno
git status                              # clean expected
git log --oneline -5                    # ostatnie commity FR-04 widoczne

# 2. Switch na main i pull
git checkout main
git pull origin main

# 3. Branch off main dla redesignu
git checkout -b feat/redesign-cinema-city-style
```

Alternatywnie: zostań na `feat/FR-04-screening-list` (mieszane PR-y nie są zalecane, ale dopuszczalne). **Powiedz w czacie, którą opcję wybierasz przed Task 1.**

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `settings/base.py` | Modify (1 linia) | Dodanie `STATICFILES_DIRS` |
| `static/css/theme.css` | Create | Design tokens (kolory, font, spacing), Bootstrap CSS variable override, aktywny nav link |
| `static/css/components.css` | Create | `.time-pill`, `.movie-card`, `.screening-card`, `.screening-day`, `.movie-hero`, `.filter-bar` |
| `templates/base.html` | Modify (rewrite) | Sticky nav z aktywnym linkiem, Inter font preconnect, dark theme, footer |
| `templates/cinema/movie_list.html` | Modify (rewrite) | Filter-bar + grid kart movie-card (plakat + overlay) |
| `templates/cinema/screening_list.html` | Modify (rewrite) | Lista screening-card z pigułkami godzin grupowanymi po sali |
| `templates/cinema/movie_detail.html` | Modify (rewrite) | Hero z rozmytym tłem + zwiastun + reżyseria + obsada-carousel (restyled) + pigułki dat |

---

## Task 1: Setup `static/` directory + STATICFILES_DIRS

**Files:**
- Create: `static/css/` (directory)
- Modify: `settings/base.py:88` (zaraz po `STATIC_URL`)

- [ ] **Step 1: Utwórz katalogi**

W terminalu (Git Bash):
```bash
mkdir -p static/css
```

- [ ] **Step 2: Dodaj `STATICFILES_DIRS` do settings**

Otwórz `settings/base.py`. Znajdź linię `STATIC_URL = "static/"` (linia 88). **Dodaj DOKŁADNIE pod nią** (między `STATIC_URL` a `MEDIA_URL`):

```python
STATICFILES_DIRS = [BASE_DIR / "static"]
```

Wynikowo fragment ma wyglądać tak:
```python
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ... reszta bez zmian
```

- [ ] **Step 3: Weryfikacja**

```bash
poetry run python manage.py check
```

Oczekiwane: `System check identified no issues (0 silenced).`

```bash
poetry run pytest -x
```

Oczekiwane: wszystkie testy zielone (regresja).

- [ ] **Step 4: Smoke test serwera**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/` — strona ładuje się jak przed zmianą (jeszcze nie ma żadnego CSS-a, nic się nie psuje). Zatrzymaj serwer (`Ctrl+C`).

- [ ] **Step 5: Commit**

```bash
git add settings/base.py
git commit -m "$(cat <<'EOF'
chore(infra): add STATICFILES_DIRS for project-level static assets

Prepares the project to serve custom CSS (theme.css, components.css) added in the
cinema-city-style redesign. No assets exist yet — this commit only wires the
settings entry pointing at BASE_DIR/static.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

> **Uwaga:** `static/css/` jest pusty na tym etapie — Git nie śledzi pustych katalogów, więc commit zawiera tylko `settings/base.py`. Katalog pojawi się w repo dopiero z plikiem CSS w Task 2.

---

## Task 2: Utwórz `static/css/theme.css`

**Files:**
- Create: `static/css/theme.css`

- [ ] **Step 1: Utwórz plik z pełną zawartością**

Utwórz `static/css/theme.css`. Wklej dokładnie poniższą zawartość:

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
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 12px;

  /* Bootstrap variable override */
  --bs-body-bg: var(--bg);
  --bs-body-color: var(--text);
  --bs-primary: var(--accent);
  --bs-primary-rgb: 139, 92, 246;
  --bs-tertiary-bg: var(--bg-elev);
  --bs-border-color: var(--border);
  --bs-link-color: var(--accent);
  --bs-link-hover-color: var(--accent-hover);
  --bs-secondary-bg: var(--bg-elev);
  --bs-emphasis-color: var(--text);
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
}

/* Typografia */
h1, .h1 { font-size: 32px; font-weight: 800; letter-spacing: -0.02em; }
h2, .h2 { font-size: 22px; font-weight: 700; }
h3, .h3 { font-size: 18px; font-weight: 700; }
.label-uppercase {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
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

/* Bootstrap form-control override (dark inputs) */
.form-control,
.form-select {
  background-color: var(--bg);
  border-color: var(--border);
  color: var(--text);
}
.form-control:focus,
.form-select:focus {
  background-color: var(--bg);
  border-color: var(--accent);
  color: var(--text);
  box-shadow: 0 0 0 0.25rem rgba(139, 92, 246, 0.25);
}
.form-control::placeholder { color: var(--text-muted); opacity: 0.6; }

/* Alert override — lekko ciemniej */
.alert {
  background-color: var(--bg-elev);
  border-color: var(--border);
  color: var(--text);
}

/* Pagination */
.page-link {
  background-color: var(--bg-elev);
  border-color: var(--border);
  color: var(--text);
}
.page-link:hover {
  background-color: var(--accent-bg);
  border-color: var(--accent);
  color: var(--text);
}
.page-item.active .page-link {
  background-color: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
```

- [ ] **Step 2: Weryfikacja istnienia pliku**

```bash
ls -la static/css/theme.css
```

Oczekiwane: plik istnieje (kilka KB).

- [ ] **Step 3: Pytest regression**

```bash
poetry run pytest -x
```

Oczekiwane: wszystkie testy zielone (theme.css jeszcze nie jest linkowany — testy nie dotyka go).

- [ ] **Step 4: Smoke test**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/static/css/theme.css` — powinien zwrócić zawartość pliku (200). Otwórz `http://127.0.0.1:8000/` — strona wygląda jak przed (CSS nie jest jeszcze podłączony w base.html). Zatrzymaj serwer.

- [ ] **Step 5: Commit**

```bash
git add static/css/theme.css
git commit -m "$(cat <<'EOF'
feat(M2): add theme.css with design tokens and Bootstrap variable override

Defines the dark + violet palette (#0f1115 bg, #8B5CF6 accent), Inter-based
typography scale, spacing/radius tokens, and overrides for Bootstrap CSS
variables (--bs-body-bg, --bs-primary, --bs-tertiary-bg, ...) so the existing
Bootstrap components pick up the new theme automatically. Includes form, alert,
and pagination overrides for dark contrast. Not yet linked from base.html.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Utwórz `static/css/components.css`

**Files:**
- Create: `static/css/components.css`

- [ ] **Step 1: Utwórz plik z pełną zawartością**

Utwórz `static/css/components.css`. Wklej:

```css
/* ============================================================
   Time-pill — godzina seansu jako klikalna pigułka
   ============================================================ */
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
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.time-pill:hover {
  border-color: var(--accent);
  background: var(--accent-bg);
  color: var(--text);
}
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

/* ============================================================
   Movie-card — karta filmu w gridzie repertuaru (poster + overlay)
   ============================================================ */
.movie-card {
  position: relative;
  display: block;
  aspect-ratio: 2/3;
  background: linear-gradient(135deg, #4a4d54 0%, #2a2d34 100%);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s;
  color: inherit;
  text-decoration: none;
}
.movie-card:hover { transform: translateY(-2px); color: inherit; }
.movie-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.movie-card__placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 48px;
  opacity: 0.6;
}
.movie-card__overlay {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  padding: 14px 12px 10px;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.92));
}
.movie-card__title {
  color: var(--text);
  font-weight: 700;
  font-size: 13px;
  line-height: 1.2;
}
.movie-card__meta {
  color: var(--text-muted);
  font-size: 10px;
  margin-top: 3px;
}

/* ============================================================
   Screening-card — film z pigułkami na liście /seanse
   ============================================================ */
.screening-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-bottom: 16px;
  display: flex;
  gap: 18px;
}
.screening-card__poster {
  width: 90px;
  flex-shrink: 0;
  aspect-ratio: 2/3;
  border-radius: 4px;
  overflow: hidden;
  background: linear-gradient(135deg, #4a4d54 0%, #2a2d34 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.screening-card__poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.screening-card__poster-placeholder {
  font-size: 28px;
  opacity: 0.6;
}
.screening-card__body { flex: 1; min-width: 0; }
.screening-card__title {
  color: var(--text);
  font-weight: 700;
  font-size: 18px;
  text-decoration: none;
}
.screening-card__title:hover { color: var(--accent); }
.screening-card__meta {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 4px;
}

/* Mobile: column layout */
@media (max-width: 575.98px) {
  .screening-card { flex-direction: column; }
  .screening-card__poster { width: 100%; max-width: 200px; }
}

/* ============================================================
   Screening-day — blok dnia na movie_detail (bez plakatu)
   ============================================================ */
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

/* ============================================================
   Movie-hero — hero na movie_detail (poster + opis + rozmyte tło)
   ============================================================ */
.movie-hero {
  position: relative;
  padding: 48px 0;
  margin-bottom: 32px;
  overflow: hidden;
  border-radius: var(--radius-lg);
}
.movie-hero__bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(40px);
  opacity: 0.4;
  transform: scale(1.2);
  z-index: 0;
}
.movie-hero__bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(15, 17, 21, 0.7);
}
.movie-hero__inner {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 32px;
  padding: 0 24px;
}
.movie-hero__poster {
  width: 220px;
  flex-shrink: 0;
  aspect-ratio: 2/3;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  background: linear-gradient(135deg, #4a4d54 0%, #2a2d34 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.movie-hero__poster img { width: 100%; height: 100%; object-fit: cover; }
.movie-hero__poster-placeholder { font-size: 64px; opacity: 0.7; }
.movie-hero__body { flex: 1; min-width: 0; padding-top: 8px; }
.movie-hero__breadcrumb {
  color: var(--text-muted);
  font-size: 12px;
  text-decoration: none;
}
.movie-hero__breadcrumb:hover { color: var(--accent); }
.movie-hero__title {
  color: var(--text);
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 8px 0 4px;
}
.movie-hero__meta {
  color: var(--text-muted);
  font-size: 14px;
  margin-bottom: 14px;
}
.movie-hero__genre-badge {
  background: var(--accent-bg);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  margin-right: 6px;
}
.movie-hero__description {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  max-width: 680px;
}
.movie-hero__cast {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 14px;
}
.movie-hero__cast strong { color: var(--text); }

/* Mobile: column layout */
@media (max-width: 767.98px) {
  .movie-hero__inner { flex-direction: column; }
  .movie-hero__poster { width: 100%; max-width: 280px; margin: 0 auto; }
  .movie-hero__title { font-size: 28px; }
}

/* ============================================================
   Filter-bar — pasek filtrów (movie_list, screening_list)
   ============================================================ */
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
.filter-bar > div {
  display: flex;
  flex-direction: column;
}
.filter-bar input,
.filter-bar select {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  width: 100%;
}
.filter-bar input:focus,
.filter-bar select:focus {
  outline: none;
  border-color: var(--accent);
}
.filter-bar label {
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  display: block;
  font-weight: 600;
}

/* ============================================================
   Bootstrap Carousel restyle (movie_detail — Obsada)
   ============================================================ */
.carousel.bg-elev-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
```

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x
```

Oczekiwane: zielone.

- [ ] **Step 3: Smoke test**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/static/css/components.css` — 200. Otwórz `/` — bez zmian (CSS jeszcze niepodłączony). Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add static/css/components.css
git commit -m "$(cat <<'EOF'
feat(M2): add components.css with redesign building blocks

Defines six reusable components used across cinema pages: time-pill (clickable
hour pill), movie-card (poster-dominant grid card), screening-card (movie row on
/seanse), screening-day (per-day block on movie detail), movie-hero (blurred-bg
hero on movie detail) and filter-bar. Each component is mobile-responsive. Not
yet referenced from templates.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Przepisz `templates/base.html`

**Files:**
- Modify: `templates/base.html` (full rewrite)

- [ ] **Step 1: Otwórz plik i podmień całą zawartość**

W `templates/base.html` zastąp całość poniższym kodem:

```django
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
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain"
                aria-controls="navMain" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navMain">
            {# `home` i `movie_list` to aliasy tej samej view; `movie_detail` traktujemy jako sekcja Repertuar #}
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
                <li class="nav-item me-lg-3">
                    <span class="navbar-text text-muted small">{{ user.email }}</span>
                </li>
                <li class="nav-item">
                    <form method="post" action="{% url 'accounts:logout' %}" class="d-inline">
                        {% csrf_token %}
                        <button type="submit" class="btn btn-outline-light btn-sm">Wyloguj</button>
                    </form>
                </li>
                {% else %}
                <li class="nav-item">
                    <a class="nav-link" href="{% url 'accounts:login' %}">Zaloguj</a>
                </li>
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
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
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

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x
```

Oczekiwane: zielone. Zwróć uwagę na testy które renderują base (np. login, register) — powinny przejść.

- [ ] **Step 3: Smoke test w przeglądarce**

```bash
poetry run python manage.py runserver
```

Sprawdź **wszystkie** URL-e (każdy musi wyglądać podobnie, nic nie ma być rozjebane):
1. `http://127.0.0.1:8000/` — czarne tło, fioletowy fragment 🎬, „Repertuar" podświetlony fioletowym dolnym borderem
2. `http://127.0.0.1:8000/seanse/` (nowa nazwa — sprawdź `urls.py` jeśli zmieniona) — „Seanse" podświetlony
3. `http://127.0.0.1:8000/accounts/login/` — formularz w ciemnym motywie, inputy z białym tekstem
4. `http://127.0.0.1:8000/accounts/register/` — to samo
5. Mobilna szerokość (DevTools, 375px) — collapsed nav działa, aktywny link ma lewy fioletowy border
6. Przewinij stronę z długą zawartością — nav przykleja się do góry

**Co jeszcze nie wygląda dobrze** (zostanie naprawione w kolejnych taskach):
- Karty filmów na `/` są nadal stare (białe pudełka z przyciskiem „Szczegóły") — będą przepisane w Task 5
- Lista seansów `/seanse/` ma starą tabelę — Task 6
- Strona szczegółów filmu ma starą strukturę — Task 7

Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add templates/base.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign base.html with sticky nav, dark theme and Inter font

Switches the global layout to the cinema-city-inspired design: sticky-top nav,
data-bs-theme="dark", Inter from Google Fonts, theme.css + components.css linked.
Adds active-link highlighting using request.resolver_match.url_name with home /
movie_list / movie_detail collapsed under the Repertuar tab. Login link becomes
a plain anchor, register becomes a solid CTA. Cinema content pages still use
their old internal structure — those are redesigned in subsequent commits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Przepisz `templates/cinema/movie_list.html`

**Files:**
- Modify: `templates/cinema/movie_list.html` (full rewrite)

- [ ] **Step 1: Otwórz plik i podmień całą zawartość**

```django
{% extends "base.html" %}

{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1">Repertuar</h1>
<p class="text-muted small mb-4">Wszystkie filmy z zaplanowanymi seansami</p>

<form method="get" class="filter-bar" role="search">
    <div style="flex:2; min-width:200px;">
        <label for="id_q">Szukaj</label>
        {{ filter_form.q }}
    </div>
    <div style="flex:1; min-width:140px;">
        <label for="id_genre">Gatunek</label>
        {{ filter_form.genre }}
    </div>
    <div style="flex:1; min-width:140px;">
        <label for="id_date">Data</label>
        {{ filter_form.date }}
    </div>
    <button type="submit" class="btn btn-primary">Filtruj</button>
    {% if request.GET %}
    <a href="{% url 'cinema:movie_list' %}" class="btn btn-outline-light" title="Wyczyść filtry" aria-label="Wyczyść filtry">×</a>
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
<nav aria-label="Paginacja" class="mt-4">
    <ul class="pagination justify-content-center">
        {% if page_obj.has_previous %}
        <li class="page-item">
            <a class="page-link" href="?{% querystring page=page_obj.previous_page_number %}" aria-label="Poprzednia strona">«</a>
        </li>
        {% endif %}
        <li class="page-item active" aria-current="page">
            <span class="page-link">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
        </li>
        {% if page_obj.has_next %}
        <li class="page-item">
            <a class="page-link" href="?{% querystring page=page_obj.next_page_number %}" aria-label="Następna strona">»</a>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}
{% else %}
<div class="alert alert-info">
    {% if request.GET %}
    Brak filmów pasujących do wybranych kryteriów.
    <a href="{% url 'cinema:movie_list' %}">Wyczyść filtry</a> żeby zobaczyć wszystkie.
    {% else %}
    Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x
```

Oczekiwane: zielone. Szczególnie testy `MovieListView` (filtrowanie, pagination, sortowanie).

- [ ] **Step 3: Smoke test w przeglądarce**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/` i sprawdź:
1. Grid kart filmów — plakaty 2:3, na 1200px+ jest 5 kolumn, na 992px 4, na 768px 4, na 576px 3, na mobile 2.
2. Tytuł + gatunki widać na DOLNYM gradiencie plakatu (białe na czarnym overlay).
3. Hover na kartę: lekkie uniesienie (translateY -2px).
4. Klik na kartę prowadzi do `movie_detail`.
5. Filter-bar: input szukania, select gatunku, date input — wszystkie w ciemnym motywie z fioletowym focusem.
6. Submit „Filtruj" z wybranym gatunkiem — wyniki filtrowane, „×" do czyszczenia widoczny.
7. Paginacja (jeśli >12 filmów): pigułki z fioletową aktywną stroną.
8. Mobile (375px): 2 kolumny, filter-bar wrap-uje się na multi-line.
9. Strona z 0 filmów (filter z bzdurą np. `?q=zzzzzz`): info alert pokazuje się w dark theme.

Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add templates/cinema/movie_list.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign movie_list with poster-dominant movie-card grid

Replaces the Bootstrap card layout (poster + title + next-screening label + CTA
button) with a poster-only "movie wall" grid where the title and genres sit on
a bottom gradient overlay. Whole card is now the clickable link to movie detail.
Grid responsive 2/3/4/4/5 columns. Filter form rendered inside .filter-bar
component with explicit labels. next_screening_at stays in the queryset
(needed for sorting) but is no longer rendered.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Przepisz `templates/cinema/screening_list.html`

**Files:**
- Modify: `templates/cinema/screening_list.html` (full rewrite)

- [ ] **Step 1: Otwórz plik i podmień całą zawartość**

```django
{% extends "base.html" %}

{% block title %}Seanse — {{ effective_date|date:"d.m.Y" }} — KinoMania{% endblock %}

{% block content %}
<h1 class="mb-1">Seanse</h1>
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
    <a href="{% url 'cinema:screening_list' %}" class="btn btn-outline-light" title="Wróć do dzisiejszego dnia">Dzisiaj</a>
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
            {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %} · {% endif %}{% endfor %}
            · {{ movie.duration_minutes }} min
        </div>

        {# regroup wymaga posortowanego inputu po grouperze — dictsort robi to w template #}
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

- [ ] **Step 2: Pytest regression (szczególnie N+1 budget)**

```bash
poetry run pytest -x
```

Oczekiwane: wszystkie testy zielone. **Krytyczny:** `test_screening_list_query_budget_regression` (commit `81adb77`) musi nadal przechodzić. `{% regroup %}` i `|dictsort` działają na danych załadowanych w pamięci, nie generują nowych queries.

Gdyby test się jednak wywalił (mało prawdopodobne): odpal go w izolacji żeby zobaczyć ile queries faktycznie:
```bash
poetry run pytest apps/cinema/tests/ -k query_budget -v
```

- [ ] **Step 3: Smoke test w przeglądarce**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/seanse/`:
1. Lista kart `.screening-card` — plakat 90×135 po lewej, meta + sekcje sal po prawej.
2. Każdy film: nazwy sal jako uppercase małym tekstem, pod nimi rząd pigułek godzin.
3. **Sortowanie**: pigułki w obrębie sali rosnąco po godzinie (`14:30, 17:00, 21:15`). Sale alfabetycznie (S1 przed S2).
4. **Bez akcentu na pigułkach domyślnie** — wszystkie neutralne (ramka `--border`). Hover: fioletowy border + tło `accent-bg`.
5. **Wyprzedane** (jeśli są w bazie — obecnie brak, `booked_seats_count()` zwraca 0): pigułka opacity 0.5 + przekreślenie.
6. Filter-bar: input typu `date` z min/max + button „Pokaż". Po wyborze przyszłej daty: nowa strona z innym `?date=`. Button „Dzisiaj" pojawia się gdy `?date=` jest w URL.
7. Mobile (375px): screening-card składa się w kolumnę (plakat na górze, body pod nim — przez media query `<576px`).
8. Edge case: data poza zakresem (`?date=2030-01-01`) — alert z `messages.warning` + lista dla `max_date`.

Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add templates/cinema/screening_list.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign screening_list with time-pill grouping by hall

Replaces the per-movie Bootstrap table (Godzina/Sala/Cena/Miejsca/Akcja) with a
.screening-card carrying poster, title, meta, and time pills regrouped by hall.
dictsort:"hall.name" pre-sort is required because Screening.Meta.ordering is by
start_time, and {% regroup %} starts a new group on every value change. Pills
default to neutral border; hover applies the accent. Sold-out pills (when
booked_seats_count > 0 lands in US-18) get strikethrough + 50% opacity. Filter
date input and "Dzisiaj" reset are reused from the previous template, restyled.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Przepisz `templates/cinema/movie_detail.html`

**Files:**
- Modify: `templates/cinema/movie_detail.html` (full rewrite)

- [ ] **Step 1: Otwórz plik i podmień całą zawartość**

```django
{% extends "base.html" %}

{% block title %}{{ movie.title }} — KinoMania{% endblock %}

{% block content %}
<article>
    {# Hero — poster + meta z rozmytym tłem z plakatu #}
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
                <a href="{% url 'cinema:movie_list' %}" class="movie-hero__breadcrumb">← Repertuar</a>
                <h1 class="movie-hero__title">{{ movie.title }}</h1>
                <div class="movie-hero__meta">
                    {{ movie.duration_minutes }} min
                    {% if movie.genres.all %} · {% for genre in movie.genres.all %}{{ genre.name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% endif %}
                    {% if movie.directors.all %} · Reż. {% for d in movie.directors.all %}{{ d.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% endif %}
                </div>
                <div class="mb-3">
                    {% for genre in movie.genres.all %}
                    <span class="movie-hero__genre-badge">{{ genre.name }}</span>
                    {% endfor %}
                </div>
                <p class="movie-hero__description">{{ movie.description|linebreaksbr }}</p>
                {% if movie.actors.all %}
                <p class="movie-hero__cast">
                    <strong>Obsada:</strong>
                    {% for a in movie.actors.all|slice:":6" %}{{ a.full_name }}{% if not forloop.last %}, {% endif %}{% endfor %}{% if movie.actors.all|length > 6 %} i inni{% endif %}
                </p>
                {% endif %}
            </div>
        </div>
    </section>

    {# Zwiastun — tylko jeśli jest URL #}
    {% if trailer_embed_url %}
    <section class="mb-5">
        <h2 class="mb-3">Zwiastun</h2>
        <iframe src="{{ trailer_embed_url }}"
                title="Zwiastun: {{ movie.title }}"
                width="100%" style="aspect-ratio: 16/9; border-radius: var(--radius-md); border: 0;"
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                referrerpolicy="strict-origin-when-cross-origin"
                sandbox="allow-scripts allow-same-origin allow-presentation"
                allowfullscreen></iframe>
    </section>
    {% elif movie.trailer_url %}
    <section class="mb-5">
        <h2 class="mb-3">Zwiastun</h2>
        <a href="{{ movie.trailer_url }}" class="btn btn-outline-light" target="_blank" rel="noopener noreferrer">Zobacz zwiastun (link zewnętrzny)</a>
    </section>
    {% endif %}

    {# Reżyseria #}
    {% if movie.directors.all %}
    <section class="mb-5">
        <h2 class="mb-3">Reżyseria</h2>
        <div class="row row-cols-2 row-cols-md-4 g-3">
            {% for director in movie.directors.all %}
            <div class="col text-center">
                {% if director.photo %}
                <img src="{{ director.photo.url }}" alt="{{ director.full_name }}"
                     class="rounded-circle mb-2"
                     style="width:80px; height:80px; object-fit:cover; border:2px solid var(--border);">
                {% else %}
                <div class="rounded-circle d-flex align-items-center justify-content-center mb-2 mx-auto"
                     style="width:80px; height:80px; font-size:2rem; background:var(--bg-elev); border:2px solid var(--border);"
                     aria-hidden="true">👤</div>
                {% endif %}
                <div class="small">{{ director.full_name }}</div>
            </div>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {# Obsada — Bootstrap Carousel zachowany, restyled #}
    {% if movie.actors.all %}
    <section class="mb-5">
        <h2 class="mb-3">Obsada</h2>
        <div id="actorsCarousel" class="carousel slide bg-elev-card" data-bs-ride="false">
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
                             style="width:140px; height:140px; font-size:3rem; background:var(--bg); border:2px solid var(--border);"
                             aria-hidden="true">👤</div>
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
    <section class="mb-5">
        <h2 class="mb-3">Nadchodzące seanse</h2>
        {% if upcoming_screenings %}
            {# upcoming_screenings z view jest posortowane po start_time ASC — regroup po dacie działa od razu #}
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

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x
```

Oczekiwane: zielone. Testy `MovieDetailView` (jeśli są) muszą przejść.

- [ ] **Step 3: Smoke test w przeglądarce**

```bash
poetry run python manage.py runserver
```

Otwórz dowolny film z `seed_db`, np. `http://127.0.0.1:8000/movies/1/`:
1. **Hero**: plakat 220×330 z cieniem, tytuł 36px, pod tytułem meta (duration · genres · reż.), badge'y gatunków w fioletowym `accent-bg`, opis z `linebreaksbr`, krótka „Obsada: …" pod opisem (top 6).
2. **Rozmyte tło hero** — przy oddanym plakatu widoczne za poster (blur 40px, opacity 0.4, dark overlay 70%).
3. **Breadcrumb** „← Repertuar" jako mały link nad tytułem.
4. **Zwiastun** — jeśli `trailer_url` istnieje: iframe YouTube z `aspect-ratio:16/9`, ramka `radius-md`.
5. **Reżyseria** — siatka 2/4 kolumn z avatarami w fioletowych obwódkach.
6. **Obsada carousel** — Bootstrap carousel z tłem `bg-elev` i ramką, strzałki działają.
7. **Nadchodzące seanse** — sekcje `.screening-day` per dzień (data po polsku: „czwartek, 21 maja"), w nich sekcje sal z pigułkami.
8. **Film bez plakatu** (np. zedytuj w admin lub utwórz w shell): hero pokazuje placeholder 🎬 zamiast obrazka, bez tła rozmytego.
9. **Film bez seansów** (przyszłych): sekcja kończy się info alertem „Brak zaplanowanych seansów".
10. **Mobile (375px)**: hero stack-uje się w kolumnę (plakat na górze 280px max), tytuł zmniejsza się do 28px.

Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add templates/cinema/movie_detail.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign movie_detail with hero, restyled sections and date-grouped pills

Adds .movie-hero (blurred poster background + sharp poster + title + meta + cast
preview) above the existing trailer / directors / actors-carousel sections, which
keep their structure and get restyled via theme.css and explicit border/background
variables. Upcoming screenings convert from a flat table to .screening-day blocks
regrouped first by date (Y-m-d) then by hall, mirroring screening_list's pills.
dictsort on hall.name before {% regroup %} guards against duplicate groups since
upcoming_screenings is ordered by start_time. Cast preview in hero is sliced to
the first 6 names with "i inni" indicator when there are more.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Final verification — pełny przegląd + cleanup

**Files:**
- (read-only) — sprawdzanie

- [ ] **Step 1: Pełny zestaw testów + coverage**

```bash
poetry run pytest --cov
```

Oczekiwane: wszystkie zielone, coverage ≥80% (próg z `pyproject.toml`).

- [ ] **Step 2: Lint + format check**

```bash
poetry run ruff check .
poetry run ruff format --check .
```

Oczekiwane: zero błędów. (Redesign nie ruszał `.py` poza `settings/base.py:88` — pojedyncza linia, format ok.)

- [ ] **Step 3: Mypy**

```bash
poetry run mypy .
```

Oczekiwane: zero błędów.

- [ ] **Step 4: Pełny checklist wizualny**

```bash
poetry run python manage.py runserver
```

Przejdź **wszystkie strony**:
1. `/` — repertuar grid 5/4/3/2 kolumn, plakat-overlay karty, filter-bar, paginacja
2. `/movies/1/` (lub inny film) — hero z rozmytym tłem, zwiastun, reżyseria, obsada-carousel, pigułki dat
3. `/seanse/` — lista screening-card z pigułkami sal
4. `/seanse/?date=YYYY-MM-DD` (jutro) — inna data, button „Dzisiaj" widoczny
5. `/seanse/?date=2030-01-01` — alert warning + lista dla `max_date`
6. `/accounts/login/` — dark formularz
7. `/accounts/register/` — dark formularz
8. `/accounts/logout/` flow — wyloguj button w nav działa
9. DevTools mobile 375px na każdej z powyższych — collapsed nav, responsive grid, screening-card kolumna

Network tab: brak 404 na fonts (Inter), brak 404 na `theme.css` ani `components.css`.

Zatrzymaj serwer.

- [ ] **Step 5: (opcjonalnie) Cleanup brainstorm files**

`/.superpowers/brainstorm/` zawiera HTML-e z towarzysza wizualnego brainstormingu. Możesz je zostawić (są w `.gitignore` jeśli go zaktualizowałeś, albo poza repo workflow) lub skasować po decyzji:

```bash
# Sprawdź czy są w .gitignore
grep -n ".superpowers" .gitignore 2>/dev/null || echo "(.superpowers nie w .gitignore — dodaj jeśli chcesz)"

# Opcjonalnie dodaj:
echo ".superpowers/" >> .gitignore
git add .gitignore
git commit -m "chore(infra): ignore .superpowers/ brainstorm session files"
```

- [ ] **Step 6: Branch wrap-up**

Jeśli pracowałeś na osobnym branchu `feat/redesign-cinema-city-style`:

```bash
git log --oneline main..HEAD          # zobacz wszystkie commity tego brancha
git push -u origin feat/redesign-cinema-city-style
gh pr create --title "feat(M2): redesign templates in cinema-city style" --body "$(cat <<'EOF'
## Summary
- Globalny redesign w stylu cinema-city.pl: dark theme + fioletowy akcent (#8B5CF6) + Inter
- Plakaty-dominanty na liście filmów, pigułki godzin na liście seansów, hero z rozmytym tłem na szczegółach
- Bez zmian backendu (models / views / urls / forms nietknięte). Tylko CSS + HTML + 1 linia settings/base.py

## Linked
- Spec: docs/superpowers/specs/2026-05-21-cinema-city-style-redesign.md
- Plan: docs/superpowers/plans/2026-05-21-cinema-city-style-redesign.md

## Definition of Done checklist
- [x] AC: 3 strony cinema + base mają nowy wygląd
- [x] Testy zielone (\`pytest --cov\`, coverage ≥80%)
- [x] \`ruff check\`, \`ruff format --check\`, \`mypy\` — czyste
- [x] Brak nowych migracji
- [x] i18n: brak nowych stringów (template'y używają istniejących pól modelu)
- [x] Manualne testy wszystkich URLi w przeglądarce (desktop + mobile)

## Test plan
- [x] /, /movies/1/, /seanse/, /accounts/* — wizualnie sprawdzone
- [x] DevTools mobile 375px — responsywność OK
- [x] N+1 budget test (test_screening_list_query_budget_regression) — zielony

## Screenshots
(do dodania ręcznie po PR — repertuar, seanse, szczegóły filmu)
EOF
)"
```

Jeśli pracowałeś na `feat/FR-04-screening-list` — redesign commity dorzucą się do PR-a FR-04 (mieszany, ale dopuszczalny per §5).

- [ ] **Step 7: (opcjonalnie) Aktualizacja memory**

Jeśli pojawiły się nowe wzorce warte zapamiętania na przyszłość (np. „dla refactorów template'ów user preferuje plan z bite-sized taskami zamiast jednego dużego commita") — zapisz przez auto-memory.

---

## Spec coverage check (self-review)

| Sekcja spec | Pokrycie w planie |
|-------------|--------------------|
| §1 Cel / out-of-scope | Header planu + założenie testowe |
| §2 Architektura plików | File Structure table + Task 1 |
| §3 Design tokens | Task 2 (theme.css) |
| §4 Komponenty CSS | Task 3 (components.css) |
| §5 base.html | Task 4 |
| §6 movie_list.html | Task 5 |
| §7 screening_list.html | Task 6 |
| §8 movie_detail.html | Task 7 |
| §9 Responsywność | Wbudowane w Task 3 (media queries) + smoke checks per task |
| §10 Testowanie | Każdy task ma `pytest -x` + browser smoke check; Task 8 ma full sweep |
| §11 Kolejność implementacji | Tasks 1→8 w tej samej kolejności |
| §12 Co dostaje / nie dostaje branch | Header + PR body w Task 8 |

Brak gaps. Plan domknięty.
