# KinoMania — Auth pages redesign (login / register / activation / resend)

**Data:** 2026-05-21
**Branch (planned):** `feat/redesign-auth-pages` (off `feat/redesign-cinema-city-style`)
**Powiązane:**
- `docs/superpowers/specs/2026-05-21-cinema-city-style-redesign.md` — bazowy redesign
- `static/css/theme.css`, `static/css/components.css` — tokens + komponenty (już istnieją)
- `templates/base.html` — sticky nav + dark theme (już zredesignowany)

---

## 1. Cel

Doprowadzić 6 stron `accounts/` (login, register, activation_sent, activation_invalid, resend, resend_done) do stylistycznej spójności z resztą KinoManii po głównym redesignie cinema-city. Obecnie strony dziedziczą `base.html` (dark + Inter), ale używają domyślnych Bootstrap `card` bez brandingu — wyglądają jak generyczny SaaS dashboard.

### Out of scope
- Zmiany w `forms.py`, `views.py`, `urls.py`, `models.py` (auth backend nie zmieniony)
- Zmiany w mechanice resend / activation (tylko prezentacja)
- Nowe pola w formach
- Dodatkowe strony auth (np. password reset — jeśli pojawią się w przyszłości, zaadaptują wzorzec `_auth_base.html`)

---

## 2. Architektura plików

### Nowe pliki

```
templates/accounts/
└── _auth_base.html       # intermediate template: branding header + card slot + footer slot
```

### Edytowane (rewrite)

```
templates/accounts/
├── login.html
├── register.html
├── activation_sent.html
├── activation_invalid.html
├── resend.html
└── resend_done.html
```

### Edytowane (append)

```
static/css/components.css  # dopisanie sekcji .auth-shell, .auth-card, .auth-brand, .auth-footer-link
```

### Stan obecny — zweryfikowane

| Element | Stan |
|---------|------|
| Wszystkie 6 templates rozszerzają `base.html` | ✅ tak |
| `theme.css` ma `.form-control`/`.form-select` override (dark inputs + fioletowy focus) | ✅ z poprzedniego redesignu |
| Testy regresji content w `tests/accounts/*.py` | ❌ brak — testy są behawioralne (forms, models, emails, login flow); template content nie testowany |
| Testy `tests/cinema/test_accounts_templates_regression.py` (sprawdzają `<nav` + `🎬 KinoMania` na auth) | ✅ przejdą — nasz `_auth_base.html` rozszerza `base.html` więc nav + brand są obecne |

---

## 3. CSS components (dopisanie do `static/css/components.css`)

```css
/* ============================================================
   Auth shell — login/register/activation/resend
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

---

## 4. `_auth_base.html` — szkielet

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

Bloki, które dzieci mogą nadpisać:
- `title` — z `base.html` (tab name)
- `auth_tagline` — krótki zachęcający tekst pod logo
- `auth_body` — zawartość karty (form lub message)
- `auth_footer` — alternatywne akcje pod kartą (opcjonalny)

**Uwaga:** Children rozszerzają `accounts/_auth_base.html`, NIE `base.html`. Hierarchia: `base.html` → `_auth_base.html` → `login.html`/etc.

---

## 5. Per-page mapping

### 5.1. `login.html`

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

### 5.2. `register.html`

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

### 5.3. `activation_sent.html`

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

### 5.4. `activation_invalid.html`

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

### 5.5. `resend.html`

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
    <button type="submit" class="btn btn-primary auth-card__submit">Wyślij</button>
</form>
{% endblock %}
```

### 5.6. `resend_done.html`

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

---

## 6. Form inputs styling

`{{ field }}` renderuje Django widget. Theme.css ma override:

```css
.form-control,
.form-select {
  background-color: var(--bg);
  border-color: var(--border);
  color: var(--text);
}
```

To zadziała JEŚLI widget renderuje się z klasą `form-control` (lub `form-select` dla `<select>`). Większość Django form widgets nie ma tej klasy domyślnie — Django zostawia gołe `<input>`.

### Konieczne sprawdzenie w `apps/accounts/forms.py`

Przed implementacją: czy widgety mają `attrs={'class': 'form-control'}`?

**Jeśli NIE mają** — dwa lekarstwa:
- A) Dodać `widget.attrs.update({'class': 'form-control'})` w `forms.py` w `__init__` każdej formy (czyste, ale ruszamy formy = poza scope?)
- B) Dodać do `theme.css` selektory dla gołych inputów wewnątrz `.auth-card__field`:
  ```css
  .auth-card__field input,
  .auth-card__field select,
  .auth-card__field textarea {
    background-color: var(--bg);
    border-color: var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 14px;
    width: 100%;
  }
  ```

**Decyzja:** opcja B (pozostajemy w CSS scope, nie ruszamy forms.py). Selektory CSS dla `.auth-card__field input/select/textarea` dodajemy do components.css. Jeśli formy MAJĄ klasę `form-control` — istniejący override z theme.css zadziała pierwszy (oba sets selektorów się zsynchronizują przez podobne reguły).

---

## 7. Testowanie

### Regresja

Wszystkie istniejące testy muszą przejść:
- `tests/accounts/*.py` — behawioralne (formy, modele, emaile), nie content templates → przejdą bez zmian
- `tests/cinema/test_accounts_templates_regression.py` — sprawdza `<nav` i `🎬 KinoMania` na auth, dziedziczone z base → przejdą

### Manualny sweep

Po implementacji obejść:
1. `/accounts/login/` — branding + form + 2 footer linki
2. `/accounts/register/` — branding + form (z polem hasła + help_text) + 1 footer link
3. `/accounts/activate/<bad-token>/` (sztuczny zły token) — 📬 invalid variant
4. `/accounts/activation-sent/` (jeśli URL istnieje — sprawdzić urls.py) lub po realnym rejestrze
5. `/accounts/activation-resend/` — form
6. Po submicie resend — `resend_done` view

### Form input check

W trakcie smoke testu: czy inputy mają ciemne tło + fioletowy focus? Jeśli nie — fallback opcja B z §6 zadziała.

---

## 8. Kolejność implementacji

1. **CSS** — dopisać `.auth-shell` / `.auth-card` / `.auth-brand` / `.auth-footer-link` + `.auth-card__field input/select/textarea` fallback do `components.css`
2. **`_auth_base.html`** — szkielet z blokami
3. **`login.html`** — najczęściej używany, sprawdzamy że pattern działa
4. **`register.html`** — drugi co do ważności + ma help_text na polach
5. **`activation_sent.html`** — pierwszy no-form variant (testuje `.auth-card__message`)
6. **`activation_invalid.html`** — drugi no-form variant + CTA w karcie
7. **`resend.html`** — form variant z hint
8. **`resend_done.html`** — trzeci no-form variant
9. **`pytest -x`** + ruff + mypy — full sweep
10. **Manualny test** w przeglądarce wszystkich 6 stron + mobile

---

## 9. Out of scope (follow-up jeśli zajdzie potrzeba)

- Password reset flow (gdy będzie wprowadzony — adaptuje wzorzec `_auth_base.html`)
- Social login buttons (out of scope projektu w ogóle)
- Rate-limit feedback UI (już jest jako Django messages na innym poziomie)
