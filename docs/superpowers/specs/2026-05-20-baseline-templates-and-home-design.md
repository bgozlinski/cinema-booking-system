# Design — KinoMania: baseline templates extract + home view (US-09)

**Data:** 2026-05-20
**Status:** Approved (pending final user review of this written spec)
**Autor:** brainstorming session — bartek + Claude (Opus 4.7)
**Powiązany US:** US-09 (`feat/M1-baseline-templates`) — ostatnia US milestone'u M1
**Powiązany FR:** UI/UX (sekcja 6 spec funkcjonalnego) + dependency dla US-11/US-13/US-14 (templates extendują `base.html`)
**Cel:** Wydzielić Bootstrap 5 baseline (`_base.html`) z `apps/accounts/templates/` do globalnego `templates/` katalogu, przenieść WSZYSTKIE template'y projektu (accounts HTML + emails) do globalnego katalogu pod namespace'ami, oraz dodać home view (`/`) renderujący placeholder landing page z hero + cards. Po US-09 cały projekt korzysta z jednolitej template'owej struktury i ma działający `/` route. Dokument NIE zawiera planu implementacyjnego — ten powstanie przez `superpowers:writing-plans` po akceptacji specu.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura i lokalizacja](#2-architektura-i-lokalizacja)
3. [Komponenty](#3-komponenty)
4. [Konfiguracja Django](#4-konfiguracja-django)
5. [Strategia testów](#5-strategia-testów)
6. [Zmiany w plikach](#6-zmiany-w-plikach)
7. [Aktualizacje dokumentacji](#7-aktualizacje-dokumentacji)
8. [Plan commitów](#8-plan-commitów)
9. [Out of scope (follow-up)](#9-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Gdzie żyje home view?** | `apps/cinema/` (nie `apps/pages/`, nie inline w `settings/urls.py`). Cinema-themed landing pasuje do app cinema; backlog hint o `tests/cinema/` potwierdza tę lokalizację. Inicjuje `apps/cinema/views.py` (po US-08 cinema miało tylko management command). |
| Q2 | **CBV czy FBV?** | `TemplateView` (`apps/cinema/views.py: HomeView`). Idiomatic Django dla static-ish content; łatwy do rozszerzenia o `get_context_data()` w M2 gdy dodamy featured movies. FBV byłby równie dobry — wybieramy CBV dla spójności z przyszłymi cinema views (M2 będzie miało listy/detale). |
| Q3 | **Treść home page (M1, brak modeli)?** | Bootstrap hero (welcome + auth-aware CTA) + trzy "coming soon" cards: Repertuar, Seanse, Konto. Repertuar/Seanse pokazują badge "Wkrótce" (placeholder do M2). Konto jest aktywne — link do login/register lub logout w zależności od auth state. |
| Q4 | **Repertuar nav link** | Aktywujemy w US-09 (href `/`, brak klasy `disabled`). Brand `🎬 KinoMania` i Repertuar oba prowadzą do home — to świadomy duplikat (Repertuar zostanie przepointowany na `/movies/` w US-11). Seanse pozostaje `disabled` do US-14. |
| Q5 | **Lokalizacja WSZYSTKICH template'ów** | Globalny `templates/` na roocie. Migrujemy KAŻDY template z `apps/accounts/templates/accounts/` do `templates/accounts/` (HTML + `emails/`). `apps/cinema/templates/` NIGDY nie powstaje — `templates/cinema/home.html` od razu trafia do globalnego. Spójna reguła: zero template'ów wewnątrz apps. |
| Q6 | **Zachowanie `APP_DIRS=True`** | Zostawiamy `True` (vestigial, ale harmless — w żadnym `apps/<x>/templates/` nic nie ma po migracji). YAGNI — nie flippujemy na `False`, żeby nie zwiększać delty US-09. |
| Q7 | **Extra blocks w `base.html`?** | NIE dodajemy `{% block extra_head %}` / `{% block extra_scripts %}`. YAGNI — dodamy gdy konkretna podstrona ich potrzebuje. |

---

## 2. Architektura i lokalizacja

### 2.1 Struktura katalogów (delta po US-09)

```
templates/                                  ★ NEW global dir (single source of truth)
├── base.html                               ★ NEW (was apps/accounts/templates/accounts/_base.html, + Repertuar→/)
├── cinema/
│   └── home.html                           ★ NEW (hero + 3 cards, extends "base.html")
└── accounts/                               ★ MOVED here from apps/accounts/templates/accounts/
    ├── login.html                          ✎ extends "base.html"
    ├── register.html                       ✎ extends "base.html"
    ├── activation_invalid.html             ✎ extends "base.html"
    ├── activation_sent.html                ✎ extends "base.html"
    ├── resend.html                         ✎ extends "base.html"
    ├── resend_done.html                    ✎ extends "base.html"
    └── emails/
        ├── activation_subject.txt          (treść bez zmian)
        └── activation_body.txt             (treść bez zmian)

apps/accounts/templates/                    ✗ DELETED — cały subdrzew znika
apps/cinema/templates/                      ✗ NEVER CREATED

apps/cinema/
├── views.py                                ★ NEW — class HomeView(TemplateView)
└── urls.py                                 ★ NEW — app_name="cinema", path("", HomeView, name="home")

settings/
├── base.py                                 ✎ TEMPLATES.DIRS = [BASE_DIR / "templates"]
└── urls.py                                 ✎ include("apps.cinema.urls") na path("")

tests/cinema/                               (istnieje od US-08)
├── test_base_template.py                   ★ NEW
├── test_home.py                            ★ NEW
└── test_accounts_templates_regression.py   ★ NEW
```

### 2.2 Dlaczego globalny `templates/`

- **Jedna reguła dla całego projektu.** Każdy nowy template (US-10..US-43) trafia do `templates/<app>/<name>.html`. Brak decyzji per-app, brak duplikacji subkatalogów.
- **Django namespacing zachowane.** `render(request, "accounts/login.html")` i `{% extends "accounts/_base.html" %}` szukają po prefixie — nazwa template'u się nie zmienia, tylko fizyczna ścieżka.
- **`emails/` razem.** `emails.py` woła `render_to_string("accounts/emails/activation_body.txt")` — name pozostaje, więc po migracji subdir `templates/accounts/emails/` jest znajdowany bez zmian w kodzie.
- **`apps/` zostaje czysto Pythonowe.** Po US-09 wszystkie `apps/<x>/` zawierają wyłącznie kod (modele, widoki, managery, formy, urls, admin, management commands, migracje). Templates są warstwą prezentacji wyodrębnioną.

### 2.3 Routing

```
/                  → HomeView (apps.cinema.views.HomeView)         [NEW]
/admin/            → admin.site.urls                                (bez zmian)
/accounts/login/   → LoginView                                      (bez zmian)
/accounts/register/→ RegistrationView                               (bez zmian)
/accounts/...      → reszta accounts (bez zmian)
```

URL `/` jest namespaced jako `cinema:home` — referowalny w template'ach przez `{% url 'cinema:home' %}`.

---

## 3. Komponenty

### 3.1 `templates/base.html`

Kopia `apps/accounts/templates/accounts/_base.html` (Bootstrap 5 baseline) z jedną zmianą funkcjonalną i jednym czyszczeniem:

**Zmiany vs. obecny `_base.html`:**
1. Navbar: link **Repertuar** — usuń klasę `disabled`, zmień `href="#"` → `href="{% url 'cinema:home' %}"`.
2. Navbar: link **Seanse** pozostaje `disabled` href="#" do US-14.
3. Brand `🎬 KinoMania` href pozostaje `"/"` — celowy duplikat z Repertuar (jak wyżej).

**Bloki Jinja/Django:**
- `{% block title %}KinoMania{% endblock %}` w `<title>`
- `{% block content %}{% endblock %}` w `<main>`
- BEZ extra blocks (`extra_head`, `extra_scripts`) — YAGNI

**Struktura HTML (bez zmian wobec `_base.html`):**
- Bootstrap 5 via CDN (CSS + bundle JS)
- `<nav>` z brand, hamburger toggler, links (Repertuar/Seanse), auth-aware right-side (login/register dla anon, user email + logout form dla zalogowanego)
- `<main class="container py-4 flex-grow-1">` z messages alerts + `{% block content %}`
- `<footer>` ze stopką (`© 2026 KinoMania · projekt edukacyjny`)

### 3.2 `templates/cinema/home.html`

```django
{% extends "base.html" %}

{% block title %}KinoMania — Twoje kino online{% endblock %}

{% block content %}
<section class="bg-primary text-white py-5 rounded mb-4">
  <div class="container text-center">
    <h1 class="display-4 fw-bold">Witaj w KinoMania</h1>
    <p class="lead">Twoje kino online — rezerwuj seanse w kilka kliknięć.</p>
    {% if user.is_authenticated %}
      <p class="mb-0">Zalogowany jako <strong>{{ user.email }}</strong></p>
    {% else %}
      <a href="{% url 'accounts:login' %}" class="btn btn-light btn-lg">Zaloguj się</a>
    {% endif %}
  </div>
</section>

<div class="row row-cols-1 row-cols-md-3 g-4">
  <div class="col"><!-- Repertuar card (disabled, "Wkrótce" badge) --></div>
  <div class="col"><!-- Seanse card (disabled, "Wkrótce" badge) --></div>
  <div class="col"><!-- Konto card (active, link auth-aware) --></div>
</div>
{% endblock %}
```

**Treść kart:**

| Card | Stan M1 | Akcja anon | Akcja zalogowany | Badge |
|---|---|---|---|---|
| **Repertuar** | Disabled | — | — | "Wkrótce" |
| **Seanse** | Disabled | — | — | "Wkrótce" |
| **Konto** | Active | "Zaloguj się" lub "Zarejestruj się" | "Wyloguj się" (form POST do `accounts:logout`) | — |

### 3.3 `apps/cinema/views.py`

```python
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "cinema/home.html"
```

Brak `get_context_data()` — `user` jest dostępny w template przez Django auth context processor (już skonfigurowany w `TEMPLATES.OPTIONS.context_processors`).

### 3.4 `apps/cinema/urls.py`

```python
from django.urls import path

from .views import HomeView

app_name = "cinema"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
]
```

### 3.5 `settings/urls.py` (modyfikacja)

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("", include("apps.cinema.urls", namespace="cinema")),
]
```

Kolejność: `path("")` na końcu — Django ewaluuje patterns top-down i `""` matchuje tylko gdy `admin/` i `accounts/` nie matchują.

---

## 4. Konfiguracja Django

### 4.1 `settings/base.py` — `TEMPLATES.DIRS`

Jedna linia:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # ← było []
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
```

`BASE_DIR` jest już zdefiniowany w `settings/base.py` (linia ~6, `Path(__file__).resolve().parent.parent`).

`APP_DIRS=True` zostawiamy — po migracji żaden `apps/<x>/templates/` nie istnieje, więc to dosł. no-op. Flippowanie na `False` to czysty refactor poza scope'em US-09.

### 4.2 Brak innych zmian w settings

- Static files: bez zmian (`STATIC_URL`, `STATIC_ROOT` jak w US-01)
- Logging, middleware, auth: bez zmian
- `INSTALLED_APPS`: bez zmian (`apps.cinema` już dodane w US-08)

---

## 5. Strategia testów

### 5.1 Pliki testowe

Wszystkie w `tests/cinema/` (utworzonym w US-08).

**`tests/cinema/test_base_template.py`** — base.html behavior (testowane przez home view, bo `base.html` w izolacji nie renderuje):

| # | Test | Co weryfikuje |
|---|---|---|
| 1 | `test_base_template_includes_navbar` | GET `/`, response zawiera `<nav` + brand "🎬 KinoMania" |
| 2 | `test_base_template_includes_footer` | GET `/`, response zawiera `© 2026 KinoMania` |
| 3 | `test_navbar_shows_login_for_anon` | anon client, link "Zaloguj" obecny, brak formu Wyloguj |
| 4 | `test_navbar_shows_logout_for_authenticated` | `client.force_login(user)`, form Wyloguj + email usera w navbar, brak linku "Zaloguj" |
| 5 | `test_navbar_repertuar_links_to_home` | response zawiera `href="/"` na linku Repertuar, brak klasy `disabled` na tym linku |

**`tests/cinema/test_home.py`** — home view behavior:

| # | Test | Co weryfikuje |
|---|---|---|
| 1 | `test_home_view_returns_200` | anon GET `/` → 200 |
| 2 | `test_home_view_uses_correct_template` | `cinema/home.html` i `base.html` obecne w `response.templates` |
| 3 | `test_home_view_shows_hero_for_anon` | anon, response zawiera CTA "Zaloguj się" w hero |
| 4 | `test_home_view_shows_user_greeting_when_authenticated` | logged-in, email usera w hero, brak CTA "Zaloguj się" w hero |
| 5 | `test_home_view_shows_coming_soon_cards` | response zawiera "Repertuar" + "Seanse" + "Konto" + "Wkrótce" badge |

**`tests/cinema/test_accounts_templates_regression.py`** — refactor smoke (templates przeniesione, nadal działają):

| # | Test | Co weryfikuje |
|---|---|---|
| 1 | `test_login_template_still_renders` | GET `/accounts/login/` → 200, response zawiera `<nav` z `base.html` |
| 2 | `test_register_template_still_renders` | GET `/accounts/register/` → 200, response zawiera `<nav` |
| 3 | `test_activation_invalid_template_still_renders` | GET `/accounts/activate/<invalid-uidb64>/<invalid-token>/` → 200, zawiera `<nav` |
| 4 | `test_resend_template_still_renders` | GET `/accounts/resend-activation/` → 200, zawiera `<nav` |

### 5.2 Co NIE jest testowane

- Email template renders — już pokryte przez `tests/accounts/test_emails.py`; nazwa template'u (`accounts/emails/...`) się nie zmienia, więc istniejące testy łapią regresje
- Bootstrap CSS ładowanie z CDN — to nie nasz kod
- Footer copyright year — kosmetyczne, zostanie zmienione w 2027
- Wewnętrzna struktura CSS-classes (np. `bg-primary`) — UI smoke, nie unit test

### 5.3 Coverage

- `apps/cinema/views.py` — 100% (jedna linia: `template_name = "cinema/home.html"`)
- `apps/cinema/urls.py` — 100%
- Global `--cov-fail-under=80` musi nadal przejść

### 5.4 Test ordering i fixtures

- Brak interdependencies — każdy test ma świeży DB przez `@pytest.mark.django_db` gdy potrzebny
- Tests odpalające bez DB (np. anon GET `/`) używają `client = Client()` z konftest
- Authenticated tests używają `UserFactory` z `tests/accounts/factories.py` + `client.force_login(user)`

---

## 6. Zmiany w plikach

### 6.1 Nowe pliki (8)

| Plik | Cel |
|---|---|
| `templates/base.html` | Bootstrap 5 baseline (kopia `_base.html` + Repertuar→/) |
| `templates/cinema/home.html` | Hero + 3 cards landing |
| `apps/cinema/views.py` | `HomeView(TemplateView)` |
| `apps/cinema/urls.py` | `path("", HomeView, name="home")` |
| `tests/cinema/test_base_template.py` | 5 testów |
| `tests/cinema/test_home.py` | 5 testów |
| `tests/cinema/test_accounts_templates_regression.py` | 4 testy |

### 6.2 Przenoszone pliki (10)

Wszystkie z `apps/accounts/templates/accounts/` → `templates/accounts/`:

```
login.html
register.html
activation_invalid.html
activation_sent.html
resend.html
resend_done.html
emails/activation_subject.txt
emails/activation_body.txt
```

Każdy z 6 HTML templates dostaje edit: `{% extends "accounts/_base.html" %}` → `{% extends "base.html" %}`.

### 6.3 Modyfikowane pliki (2)

| Plik | Zmiana |
|---|---|
| `settings/base.py` | `TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]` (1 linia) |
| `settings/urls.py` | Dodać `path("", include("apps.cinema.urls", namespace="cinema"))` na końcu listy |

### 6.4 Usuwane pliki (1)

| Plik | Powód |
|---|---|
| `apps/accounts/templates/accounts/_base.html` | Zastąpione przez `templates/base.html` |

Cały subdrzew `apps/accounts/templates/` znika po przeniesieniu zawartości.

---

## 7. Aktualizacje dokumentacji

### 7.1 `.Claude/backlog.md`

- US-09 sekcja: zmienić **DoR** na `[✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)`
- US-09 sekcja: dodać linki do spec + plan (jak w US-08)
- Status board (§7): `In Progress (WIP=1)` z `_none_` na **US-09**; `Done` z US-01..US-07 na US-01..US-08
- Milestone summary: bump 7/9 → 8/9 progress (już zrobione w docs commit z US-08; teraz US-08 done, US-09 in progress)

### 7.2 `.Claude/KinoMania_wymagania_funkcjonalne.md`

Brak edycji — US-09 nie wprowadza nowych FR, jest UI/UX baseline'em wynikającym z sekcji 6 spec funkcjonalnego.

### 7.3 `memory/project_kinomania_bootstrap.md`

Po merge:
- Bump M1 progress: `8/9 → 9/9 US done` (M1 complete!)
- Update "Następny task" na **M2 planning** (US-10..US-17, decyzja `v0.1.0` tag release)
- Note: globalny `templates/` katalog istnieje, wszystkie templates pod namespace'ami, `apps/<x>/templates/` nie używamy

---

## 8. Plan commitów

Sekwencja planowanych commitów (final detail w implementation plan):

1. `docs(M1): scope US-09 baseline templates + home view` — backlog DoR + spec/plan links
2. `chore(M1): create global templates/ directory + TEMPLATES.DIRS` — settings + empty `templates/` directory
3. `feat(M1): extract base.html to global templates/ + activate Repertuar link` — `templates/base.html` (Repertuar→/), keep `accounts/_base.html` tymczasowo (kompatybilność testów)
4. `refactor(M1): move accounts templates to global templates/accounts/` — `git mv` 6 HTML + emails + edit `{% extends %}` → `base.html`, delete `accounts/_base.html`
5. `feat(M1): HomeView at / + cinema urls` — `apps/cinema/views.py`, `apps/cinema/urls.py`, `settings/urls.py` include
6. `feat(M1): home.html landing page (hero + coming-soon cards)` — `templates/cinema/home.html`
7. `test(M1): cover base.html navbar + auth-aware rendering` — `tests/cinema/test_base_template.py`
8. `test(M1): cover HomeView + home.html content` — `tests/cinema/test_home.py`
9. `test(M1): regression smoke for moved accounts templates` — `tests/cinema/test_accounts_templates_regression.py`
10. `docs(M1): mark US-09 done, M1 complete` — backlog status board update

Plan może te kroki przegrupować (TDD-style: tests-first per AC). Final sekwencja w implementation plan.

---

## 9. Out of scope (follow-up)

| # | Co | Gdzie wpada |
|---|---|---|
| 1 | Repertuar link → `/movies/` | US-11 (movie list view, M2) |
| 2 | Seanse link → `/screenings/` | US-14 (screening list, M2) |
| 3 | Featured movies on home (Today's premiere) | M2 (po US-10..US-15) lub M3 |
| 4 | `APP_DIRS=False` flip | Standalone refactor lub nigdy (vestigial harmless) |
| 5 | Custom 404/500 templates | M3 lub M4 |
| 6 | i18n (`{% trans %}` tags w templates) | Out of scope całego v1 (spec PL-only) |
| 7 | Dark mode toggle | Out of scope całego v1 |
| 8 | Footer links (About, Terms, Privacy) | Out of scope (post-MVP) |

---

**Done criteria specu:** plan implementacji (`docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md`) wygenerowany przez `superpowers:writing-plans` z tego specu i zaakceptowany.
