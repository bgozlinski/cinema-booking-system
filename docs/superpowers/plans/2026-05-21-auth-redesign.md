# KinoMania — Auth Pages Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Doprowadzić 6 stron `accounts/` (login, register, activation_sent, activation_invalid, resend, resend_done) do spójności z resztą KinoManii — branding header (🎬 + KinoMania + tagline) nad kartą formularza, dark theme, fioletowe akcenty.

**Architecture:** Nowy intermediate template `accounts/_auth_base.html` rozszerza `base.html` i definiuje 3 bloki (`auth_tagline`, `auth_body`, `auth_footer`). 6 dziecięcych templates rozszerza `_auth_base.html` i wypełnia tylko bloki — DRY. CSS dla auth idzie do istniejącego `components.css` (sekcje `.auth-shell` / `.auth-card` / `.auth-brand` / `.auth-footer-link`). Bez zmian backendu (`forms.py`/`views.py`/`urls.py`/`models.py`).

**Tech Stack:** Django 6 templates (`{% extends %}` + `{% block %}`), Bootstrap 5.3.3 (form-control inputs, `.btn-primary`), custom CSS components.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-21-auth-redesign.md`.

**Założenie testowe:** Brak nowych unit testów. Behawioralne testy z `tests/accounts/*.py` przejdą bez zmian (testują logikę, nie templates). Regression testy z `tests/cinema/test_accounts_templates_regression.py` przejdą bo `_auth_base.html` dziedziczy z `base.html` (nav + `🎬 KinoMania` obecne).

**Role division (per `.Claude/commit_convention.md` §10):**
- Claude podaje pełną zawartość plików w blokach.
- User kopiuje do plików w PyCharm i uruchamia wszystkie komendy.

**⚠️ Uwaga PyCharm:** Z poprzedniej sesji wiemy że PyCharm hard-wrap rozjebuje Django template tags (`{% %}` i `{{ }}` nie mogą być w wielu liniach). Upewnij się przed startem: `Settings → Editor → Code Style → HTML → Wrapping and Braces → Hard wrap at: 200+`.

---

## Branch Strategy

Pre-Task-1 — utwórz nowy branch off `feat/redesign-cinema-city-style` (zawiera niezbędne `theme.css` + `components.css`):

```bash
# Sanity check — nadal na branchu redesign
git status
git branch --show-current   # → feat/redesign-cinema-city-style

# Nowy branch dla auth redesignu
git checkout -b feat/redesign-auth-pages
git branch --show-current   # → feat/redesign-auth-pages
```

Po zmergowaniu `feat/redesign-cinema-city-style` do main, ten branch rebase'uj się na main: `git checkout main && git pull && git checkout feat/redesign-auth-pages && git rebase main`.

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `static/css/components.css` | Modify (append) | Dopisanie `.auth-shell` / `.auth-card` / `.auth-brand` / `.auth-footer-link` + fallback dla gołych `.auth-card__field input/select/textarea` |
| `templates/accounts/_auth_base.html` | Create | Intermediate template: branding header + card slot + footer slot |
| `templates/accounts/login.html` | Modify (rewrite) | Form login (email/password) + 2 footer linki |
| `templates/accounts/register.html` | Modify (rewrite) | Form register z `help_text` + 1 footer link |
| `templates/accounts/activation_sent.html` | Modify (rewrite) | No-form variant: 📬 + message + 1 footer link |
| `templates/accounts/activation_invalid.html` | Modify (rewrite) | No-form variant: ⚠️ + message + CTA w karcie |
| `templates/accounts/resend.html` | Modify (rewrite) | Form resend (email) + hint |
| `templates/accounts/resend_done.html` | Modify (rewrite) | No-form variant: 📨 + message |

---

## Task 1: Dopisać auth components do `static/css/components.css`

**Files:**
- Modify: `static/css/components.css` (append na końcu pliku)

- [ ] **Step 1: Otwórz `static/css/components.css`, na samym końcu dopisz:**

```css

/* ============================================================
   Auth pages (login / register / activation / resend)
   ============================================================ */
.auth-shell {
  max-width: 420px;
  margin: 48px auto;
  text-align: center;
}

.auth-brand { margin-bottom: 24px; }
.auth-brand__emoji {
  font-size: 40px;
  line-height: 1;
  margin-bottom: 8px;
}
.auth-brand__title {
  color: var(--text);
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
}
.auth-brand__tagline {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
}

.auth-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 28px 24px;
  text-align: left;
}
.auth-card__title {
  color: var(--text);
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 6px;
}
.auth-card__hint {
  color: var(--text-muted);
  font-size: 12px;
  margin: 0 0 18px;
}
.auth-card__field { margin-bottom: 14px; }
.auth-card__field-label {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.auth-card__field input,
.auth-card__field select,
.auth-card__field textarea {
  background-color: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  width: 100%;
  font-family: inherit;
}
.auth-card__field input:focus,
.auth-card__field select:focus,
.auth-card__field textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 0.25rem rgba(139, 92, 246, 0.25);
}
.auth-card__field-error {
  color: var(--danger);
  font-size: 12px;
  margin-top: 4px;
}
.auth-card__field-help {
  color: var(--text-muted);
  font-size: 11px;
  margin-top: 4px;
}
.auth-card__submit {
  width: 100%;
  margin-top: 6px;
}

/* No-form variant: emoji + message (activation_sent, activation_invalid, resend_done) */
.auth-card__message {
  text-align: center;
  padding: 8px 0;
}
.auth-card__message-emoji {
  font-size: 56px;
  line-height: 1;
  margin-bottom: 12px;
}
.auth-card__message-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
}
.auth-card__message-hint {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 8px;
}

.auth-footer-link {
  text-align: center;
  margin-top: 18px;
  color: var(--text-muted);
  font-size: 13px;
}
.auth-footer-link a { color: var(--accent); text-decoration: none; }
.auth-footer-link a:hover { color: var(--accent-hover); text-decoration: underline; }
.auth-footer-link__divider { margin: 4px 0; }

/* Mobile: padding tweaks */
@media (max-width: 575.98px) {
  .auth-shell { margin: 24px 16px; }
  .auth-card { padding: 20px 16px; }
}
```

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: wszystkie zielone (CSS nie jest jeszcze używany — testy template'ów nie zmieniają się).

- [ ] **Step 3: Smoke test ścieżki statics**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/static/css/components.css` — 200 OK, w zawartości pojawia się sekcja `Auth pages`. Otwórz `/accounts/login/` — wygląda wciąż jak obecnie (centered Bootstrap card). CSS jeszcze nieużywany. Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add static/css/components.css
git commit -m "$(cat <<'EOF'
feat(M2): add auth component CSS (auth-shell, auth-card, auth-brand)

Extends components.css with the auth pages building blocks: .auth-shell wrapper
(420px centered), .auth-brand header (emoji + title + tagline), .auth-card with
field/title/hint/message variants, and .auth-footer-link for alt actions. Field
inputs get explicit dark-theme styling via .auth-card__field input/select/textarea
selectors so bare Django widgets (without form-control class) still render correctly.
Templates not yet rewritten — done in subsequent commits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Utworzyć `templates/accounts/_auth_base.html`

**Files:**
- Create: `templates/accounts/_auth_base.html`

- [ ] **Step 1: Utwórz plik z zawartością:**

```django
{% extends "base.html" %}

{% block content %}
<div class="auth-shell">
    <div class="auth-brand">
        <div class="auth-brand__emoji" aria-hidden="true">🎬</div>
        <h1 class="auth-brand__title">KinoMania</h1>
        <p class="auth-brand__tagline">{% block auth_tagline %}{% endblock %}</p>
    </div>

    <div class="auth-card">
        {% block auth_body %}{% endblock %}
    </div>

    {% block auth_footer %}{% endblock %}
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest regression**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. `_auth_base.html` nie jest jeszcze rozszerzany przez żadną stronę.

- [ ] **Step 3: Commit**

```bash
git add templates/accounts/_auth_base.html
git commit -m "$(cat <<'EOF'
feat(M2): add accounts/_auth_base.html intermediate template

Defines the shared auth-page skeleton (auth-shell wrapper + branding header with
🎬 KinoMania logo and a per-page tagline + auth-card content slot + optional
auth-footer slot). Children will extend this instead of base.html directly to
avoid repeating the branding markup six times. No child templates rewritten yet.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Przepisać `templates/accounts/login.html`

**Files:**
- Modify: `templates/accounts/login.html` (full rewrite)

- [ ] **Step 1: Otwórz plik w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Logowanie — KinoMania{% endblock %}
{% block auth_tagline %}Zaloguj się, żeby zarezerwować bilety{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">Logowanie</h2>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% for error in field.errors %}<div class="auth-card__field-error">{{ error }}</div>{% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">Zaloguj się</button>
</form>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    <a href="{% url 'accounts:activation_resend' %}">Nie dostałeś emaila aktywacyjnego?</a>
    <div class="auth-footer-link__divider"></div>
    Nie masz konta? <a href="{% url 'accounts:register' %}">Zarejestruj się</a>
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. Szczególnie:
- `tests/accounts/test_login.py` (behavioral — form submit, redirects)
- `tests/cinema/test_accounts_templates_regression.py::test_login_template_still_renders` (sprawdza `<nav` + `🎬 KinoMania` — nadal obecne przez dziedziczenie)

- [ ] **Step 3: Smoke test**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/accounts/login/`:
1. Pod nav: branding 🎬 + „KinoMania" (24px, bold) + tagline „Zaloguj się, żeby zarezerwować bilety"
2. Karta `bg-elev` z border, 420px max-width, wycentrowana
3. Tytuł karty „Logowanie" (18px, bold)
4. Pola formularza z uppercase labelami („EMAIL", „HASŁO"), ciemne inputy z fioletowym focus
5. Submit „Zaloguj się" — full width, fioletowy
6. Pod kartą 2 linki: „Nie dostałeś emaila aktywacyjnego?" + „Nie masz konta? Zarejestruj się"
7. **Test błędu:** wpisz złe hasło → komunikat błędu (alert-danger lub field-error) w karcie
8. Mobile 375px (DevTools): margines 16px po bokach, padding karty 20px

Zatrzymaj serwer.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/login.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/login.html with branding header and auth-card

Extends accounts/_auth_base.html instead of base.html. Branding sits above the
card via the auth_tagline block; the form uses .auth-card__field markup with
uppercase labels matching the rest of the design system. Alt actions (resend
email link, register link) move to .auth-footer-link below the card.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Przepisać `templates/accounts/register.html`

**Files:**
- Modify: `templates/accounts/register.html` (full rewrite)

- [ ] **Step 1: Otwórz w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Rejestracja — KinoMania{% endblock %}
{% block auth_tagline %}Stwórz konto i zacznij rezerwować{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">Rejestracja</h2>
<p class="auth-card__hint">Po wysłaniu formularza otrzymasz email z linkiem aktywacyjnym.</p>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% if field.help_text %}
        <div class="auth-card__field-help">{{ field.help_text|safe }}</div>
        {% endif %}
        {% for error in field.errors %}<div class="auth-card__field-error">{{ error }}</div>{% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">Zarejestruj się</button>
</form>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    Masz już konto? <a href="{% url 'accounts:login' %}">Zaloguj się</a>
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. Szczególnie `tests/accounts/test_registration.py`.

- [ ] **Step 3: Smoke test**

```bash
poetry run python manage.py runserver
```

Otwórz `http://127.0.0.1:8000/accounts/register/`:
1. Branding + tagline „Stwórz konto i zacznij rezerwować"
2. Karta z tytułem „Rejestracja" + hint
3. Pola — sprawdź czy hasło ma `help_text` widoczny pod inputem (Django domyślnie generuje listę wymagań hasła)
4. **Test walidacji:** wprowadź zbyt krótkie hasło → field-error pod polem hasła
5. Submit „Zarejestruj się"
6. Footer link: „Masz już konto? Zaloguj się"

Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/register.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/register.html with branding header and auth-card

Mirrors the login redesign — branding header via auth_tagline block, form fields
with uppercase labels and help_text rendered through .auth-card__field-help.
Footer link points back to login for users who already have an account.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Przepisać `templates/accounts/activation_sent.html`

**Files:**
- Modify: `templates/accounts/activation_sent.html` (full rewrite)

- [ ] **Step 1: Otwórz w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Sprawdź skrzynkę — KinoMania{% endblock %}
{% block auth_tagline %}Email wysłany{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">📬</div>
    <p class="auth-card__message-text">Wysłaliśmy link aktywacyjny na podany adres. Kliknij w niego, aby aktywować konto.</p>
    <p class="auth-card__message-hint">Link jest ważny przez 3 dni. Nie widzisz emaila? Sprawdź folder spam.</p>
</div>
{% endblock %}

{% block auth_footer %}
<div class="auth-footer-link">
    <a href="{% url 'accounts:activation_resend' %}">Wyślij link ponownie</a>
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 3: Smoke test**

Zarejestruj nowego użytkownika (`/accounts/register/`) — po submit będziesz przekierowany do `/accounts/activation-sent/` (lub podobny URL — sprawdź `urls.py`). Albo otwórz URL bezpośrednio jeśli widok jest niezabezpieczony.

Sprawdź:
1. Branding + tagline „Email wysłany"
2. Wielki emoji 📬 (56px) wycentrowany w karcie
3. Pod nim biały tekst „Wysłaliśmy link aktywacyjny..."
4. Hint o 3 dniach + folderze spam
5. Footer link „Wyślij link ponownie"

Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/activation_sent.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/activation_sent.html with message variant

Uses .auth-card__message no-form variant (56px emoji 📬 + body text + hint)
instead of the full Bootstrap card layout. The 'Wyślij link ponownie' action
moves to the .auth-footer-link below the card.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Przepisać `templates/accounts/activation_invalid.html`

**Files:**
- Modify: `templates/accounts/activation_invalid.html` (full rewrite)

- [ ] **Step 1: Otwórz w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Link nieprawidłowy — KinoMania{% endblock %}
{% block auth_tagline %}Link nieprawidłowy lub wygasł{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">⚠️</div>
    <p class="auth-card__message-text">Link aktywacyjny jest nieprawidłowy lub wygasł.</p>
    <p class="auth-card__message-hint">Możliwe przyczyny: link został już użyty, hasło zostało w międzyczasie zmienione, albo link jest starszy niż 3 dni.</p>
    <div class="mt-4">
        <a href="{% url 'accounts:activation_resend' %}" class="btn btn-primary">Wyślij link ponownie</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. Szczególnie `tests/accounts/test_activation.py`.

- [ ] **Step 3: Smoke test**

Otwórz URL aktywacji z fake'owym tokenem, np. `http://127.0.0.1:8000/accounts/activate/abc/badtoken/` (struktura URL-a z `urls.py`):
1. Branding + tagline „Link nieprawidłowy lub wygasł"
2. Wielki ⚠️ (56px)
3. Główny komunikat + hint o przyczynach
4. **CTA button w karcie** (nie footer): „Wyślij link ponownie" jako solid `.btn-primary`

Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/activation_invalid.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/activation_invalid.html with message variant + inline CTA

No-form variant with ⚠️ emoji + error message + hint. Unlike activation_sent
which puts the resend link in the footer, this template puts the resend CTA
inside the card as a primary button — user just hit a dead end and needs a
direct, prominent recovery action.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Przepisać `templates/accounts/resend.html`

**Files:**
- Modify: `templates/accounts/resend.html` (full rewrite)

- [ ] **Step 1: Otwórz w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Wyślij ponownie link — KinoMania{% endblock %}
{% block auth_tagline %}Wyślij ponownie link aktywacyjny{% endblock %}

{% block auth_body %}
<h2 class="auth-card__title">Resend</h2>
<p class="auth-card__hint">Wpisz email użyty przy rejestracji — jeśli konto czeka na aktywację, wyślemy nowy link.</p>
<form method="post" novalidate>
    {% csrf_token %}
    {% for field in form %}
    <div class="auth-card__field">
        <label for="{{ field.id_for_label }}" class="auth-card__field-label">{{ field.label }}</label>
        {{ field }}
        {% for error in field.errors %}<div class="auth-card__field-error">{{ error }}</div>{% endfor %}
    </div>
    {% endfor %}
    {% if form.non_field_errors %}
    <div class="alert alert-danger">{{ form.non_field_errors }}</div>
    {% endif %}
    <button type="submit" class="btn btn-primary auth-card__submit">Wyślij</button>
</form>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. Szczególnie `tests/accounts/test_resend.py`.

- [ ] **Step 3: Smoke test**

Otwórz `http://127.0.0.1:8000/accounts/activation-resend/`:
1. Branding + tagline „Wyślij ponownie link aktywacyjny"
2. Karta z tytułem „Resend" + hint
3. Single field „EMAIL" + submit „Wyślij"
4. **Test:** submit z istniejącym email → przekierowanie do `resend_done` (Task 8)

Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/resend.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/resend.html with branding header and auth-card

Form variant mirroring login/register: branding header above the card, a single
email field with uppercase label, "Wyślij" submit button. The hint explains the
no-leak behaviour ("if the account is awaiting activation we send a new link")
matching the resend_done message wording.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Przepisać `templates/accounts/resend_done.html`

**Files:**
- Modify: `templates/accounts/resend_done.html` (full rewrite)

- [ ] **Step 1: Otwórz w PyCharm, `Ctrl+A`, usuń, wklej:**

```django
{% extends "accounts/_auth_base.html" %}

{% block title %}Wysłane — KinoMania{% endblock %}
{% block auth_tagline %}Wysłane{% endblock %}

{% block auth_body %}
<div class="auth-card__message">
    <div class="auth-card__message-emoji" aria-hidden="true">📨</div>
    <p class="auth-card__message-text">Jeśli konto o podanym adresie email istnieje i nie zostało jeszcze aktywowane, wysłaliśmy nowy link aktywacyjny.</p>
    <p class="auth-card__message-hint">Link jest ważny przez 3 dni.</p>
</div>
{% endblock %}
```

- [ ] **Step 2: Pytest**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 3: Smoke test**

Po submicie z Task 7 (resend form) zostaniesz przekierowany tutaj. Sprawdź:
1. Branding + tagline „Wysłane"
2. Wielki 📨 (56px)
3. Komunikat (nieujawniający czy konto istnieje — privacy)
4. Hint o 3 dniach

Zatrzymaj.

- [ ] **Step 4: Commit**

```bash
git add templates/accounts/resend_done.html
git commit -m "$(cat <<'EOF'
feat(M2): redesign accounts/resend_done.html with message variant

No-form variant: 📨 emoji + the privacy-preserving "if the account exists" message
(unchanged wording — same constraint as the original to avoid user enumeration)
+ 3-day validity hint. Same .auth-card__message pattern as activation_sent.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Final verification + PR

- [ ] **Step 1: Pełen pytest + coverage**

```bash
poetry run pytest --cov
```

Oczekiwane: 293 passed (lub więcej — bez utraty), coverage ≥80%.

- [ ] **Step 2: Lint + format + mypy**

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

Oczekiwane: zero błędów.

- [ ] **Step 3: Pełny browser sweep**

```bash
poetry run python manage.py runserver
```

Przejdź **wszystkie 6 stron**:
1. `/accounts/login/` — form variant, 2 footer linki
2. `/accounts/register/` — form variant + help_text + 1 footer link
3. `/accounts/activate/<fake-token>/` (sztucznie zły token) — message variant z ⚠️ + inline CTA
4. `/accounts/activation-sent/` (lub po realnym rejestrze) — 📬 + footer link
5. `/accounts/activation-resend/` — form variant + hint
6. Po submit `/accounts/activation-resend/` — `resend_done` 📨

Plus negative checks:
- Nav widoczny u góry każdej (sticky, fioletowe linki)
- Logo „🎬 KinoMania" wewnątrz auth-brand + dodatkowo w nav
- Mobile 375px każdej: margin 16px, padding 16px karty, branding nadal widoczny

Zatrzymaj.

- [ ] **Step 4: Sprawdź historię commitów**

```bash
git log --oneline main..HEAD
```

Oczekiwane: 8 commitów (1 CSS + 1 _auth_base + 6 templates).

Wszystkie powinny być prefixed `feat(M2):` (poza Task 1 który może być debate'owalny — też feat(M2)).

- [ ] **Step 5: Push + PR**

```bash
git push -u origin feat/redesign-auth-pages
gh pr create --title "feat(M2): redesign accounts/* templates with branding header" --body "$(cat <<'EOF'
## Summary
- Redesign 6 stron \`templates/accounts/\` (login, register, activation_sent, activation_invalid, resend, resend_done) zgodnie ze stylem cinema-city
- Branding header (🎬 + KinoMania + tagline) nad kartą; form variant (login/register/resend) i message variant (activation_sent/invalid/resend_done)
- Nowy intermediate template \`accounts/_auth_base.html\` (DRY — szkielet używany przez wszystkie 6 dzieci)
- Bez zmian backendu (forms / views / urls / models nietknięte)
- Bez nowych testów — istniejące behavioral testy z \`tests/accounts/\` i regression z \`tests/cinema/test_accounts_templates_regression.py\` pozostają zielone

## Linked
- Spec: \`docs/superpowers/specs/2026-05-21-auth-redesign.md\`
- Plan: \`docs/superpowers/plans/2026-05-21-auth-redesign.md\`
- Bazuje na: PR \`feat(M2): redesign templates in cinema-city style\` (musi zmergeować się pierwszy lub zrebase tego brancha na main)

## Definition of Done checklist
- [x] AC: wszystkie 6 stron auth ma nowy wygląd z brandingiem
- [x] Testy zielone (\`pytest --cov\`)
- [x] Coverage ≥80%
- [x] \`ruff check\`, \`ruff format --check\`, \`mypy\` — czyste
- [x] Brak nowych migracji
- [x] i18n: bez nowych user-facing stringów (tagline'y to nowe, ale to natywny PL projekt, gettext_lazy do M5)
- [x] Manualne testy w przeglądarce (desktop + mobile)

## Test plan
- [x] /accounts/login/ — branding + form + 2 footer linki + walidacja
- [x] /accounts/register/ — branding + form + help_text + 1 footer link + walidacja
- [x] /accounts/activation-sent/ — 📬 variant + footer link
- [x] /accounts/activate/<bad-token>/ — ⚠️ variant + inline CTA
- [x] /accounts/activation-resend/ — form variant + submit flow
- [x] /accounts/activation-resend/ done — 📨 variant
- [x] DevTools mobile 375px — wszystkie strony

## Out of scope (follow-up)
- Password reset flow (gdy zostanie dodany — zaadaptuje wzorzec \`_auth_base.html\`)
EOF
)"
```

Wklej URL PR-a po utworzeniu.

---

## Spec coverage check (self-review)

| Sekcja spec | Pokrycie w planie |
|-------------|--------------------|
| §1 Cel / out-of-scope | Header + założenie testowe |
| §2 Architektura plików | File Structure table + tasks 1-8 |
| §3 CSS components | Task 1 |
| §4 `_auth_base.html` skeleton | Task 2 |
| §5 Per-page mapping (5.1-5.6) | Tasks 3-8 — każda strona ma własny task |
| §6 Form inputs styling | Task 1 zawiera `.auth-card__field input/select/textarea` fallback (opcja B z spec'a) |
| §7 Testowanie | Każdy task ma `pytest -x` + browser smoke; Task 9 ma full sweep |
| §8 Kolejność implementacji | Tasks 1→9 w tej samej kolejności |
| §9 Out of scope | PR body w Task 9 |

Brak gaps. Plan domknięty.
