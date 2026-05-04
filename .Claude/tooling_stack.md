# KinoMania — Tooling Stack

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązane dokumenty:** `KinoMania_wymagania_funkcjonalne.md`, `workflow_scrum_agile.md`

> **Cel dokumentu:** kanoniczne konfiguracje narzędzi w jednym miejscu. Konfigi z tego pliku są kopiowane przez usera do odpowiednich plików projektu w trakcie milestone'a M1 (US-01..US-05). Claude trzyma się tych decyzji jako Tech Lead — żadne narzędzie spoza tej listy bez eskalacji do usera (per `workflow_scrum_agile.md` §8).

---

## 1. Zależności (Poetry) — `pyproject.toml`

**`[tool.poetry.dependencies]`:**
```toml
python = "^3.13"
django = "^6.0"
djangorestframework = "^3.15"
djangorestframework-simplejwt = "^5.3"
drf-spectacular = "^0.27"
django-environ = "^0.11"
django-filter = "^24.0"
psycopg = {extras = ["binary"], version = "^3.2"}
pillow = "^11.0"
stripe = "^11.0"
gunicorn = "^23.0"   # do prod
```

**`[tool.poetry.group.dev.dependencies]`:**
```toml
pytest = "^8.3"
pytest-django = "^4.9"
pytest-cov = "^6.0"
pytest-mock = "^3.14"
factory-boy = "^3.3"
faker = "^30.0"
ruff = "^0.7"
mypy = "^1.13"
django-stubs = {extras = ["compatible-mypy"], version = "^5.1"}
djangorestframework-stubs = {extras = ["compatible-mypy"], version = "^3.15"}
pre-commit = "^4.0"
django-debug-toolbar = "^4.4"
ipython = "^8.29"
```

---

## 2. Ruff — `pyproject.toml`

```toml
[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = ["migrations", "media", "static", "locale"]

[tool.ruff.lint]
select = [
    "E", "F", "W",      # pycodestyle + pyflakes
    "I",                 # isort
    "B",                 # bugbear
    "UP",                # pyupgrade
    "DJ",                # flake8-django
    "SIM",               # simplify
    "C4",                # comprehensions
    "RET",               # return
    "PT",                # pytest-style
    "RUF",               # ruff-specific
]
ignore = ["E501"]   # line length handled by formatter

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101"]   # asserts allowed in tests
"**/settings/*.py" = ["F405", "F403"]
```

---

## 3. Mypy — `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.13"
strict_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_untyped_defs = false   # luźniej w M1, zaostrzymy w M5
check_untyped_defs = true
plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]

[[tool.mypy.overrides]]
module = ["*.migrations.*", "*.tests.*"]
ignore_errors = true

[tool.django-stubs]
django_settings_module = "settings.dev"
```

---

## 4. Pytest — `pyproject.toml`

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "settings.dev"
python_files = ["test_*.py", "tests.py"]
addopts = [
    "--cov=accounts",
    "--cov=cinema",
    "--cov=payments",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",
    "--reuse-db",          # przyspiesza, gdy zmiana migracji daj --create-db
    "-ra",                  # show summary of all non-passing
]
markers = [
    "integration: integration tests (slower)",
    "stripe: tests touching Stripe (mocked)",
]
```

---

## 5. Coverage — `pyproject.toml`

```toml
[tool.coverage.run]
source = ["accounts", "cinema", "payments"]
omit = [
    "*/migrations/*",
    "*/tests/*",
    "*/factories.py",
    "manage.py",
    "settings/*",
]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

---

## 6. Pre-commit — `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: check-merge-conflict
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [django-stubs, djangorestframework-stubs]
  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest (fast subset)
        entry: poetry run pytest -x -m "not integration" --no-cov
        language: system
        pass_filenames: false
        stages: [pre-push]   # tylko przy push, nie przy każdym commicie
```

**Filozofia:** lint/format/mypy → przy każdym commit. Testy → przy push (żeby commit był szybki).

---

## 7. GitHub Actions CI — `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install poetry && poetry install
      - run: poetry run ruff check .
      - run: poetry run ruff format --check .
      - run: poetry run mypy .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: kinomania_test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install poetry && poetry install
      - run: poetry run pytest --cov-fail-under=80
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/kinomania_test
          SECRET_KEY: ci-secret
          STRIPE_SECRET_KEY: sk_test_dummy
          STRIPE_WEBHOOK_SECRET: whsec_dummy
      - uses: actions/upload-artifact@v4
        with: { name: coverage-html, path: htmlcov/ }
```

---

## 8. Docker Compose — `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: kinomania
      POSTGRES_USER: kinomania
      POSTGRES_PASSWORD: kinomania
    ports: ["5432:5432"]
    volumes: [pg_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kinomania"]
      interval: 5s
      retries: 10
volumes:
  pg_data:
```

**Stripe webhook lokalnie:**
```bash
stripe listen --forward-to localhost:8000/webhooks/stripe/
```
Skopiuj wyświetlony `whsec_…` do `STRIPE_WEBHOOK_SECRET` w `.env`. Instalacja Stripe CLI: https://docs.stripe.com/stripe-cli.

---

## 9. `.env.example`

```ini
DEBUG=True
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://kinomania:kinomania@localhost:5432/kinomania
LANGUAGE_CODE=pl
TIME_ZONE=Europe/Warsaw

# Stripe (test mode keys from dashboard.stripe.com/test)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=pln

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MIN=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# DRF throttling
THROTTLE_ANON=100/hour
THROTTLE_USER=1000/hour
THROTTLE_AUTH=20/hour
```

---

## 10. Factory Boy — konwencja

**Lokalizacja:** `accounts/factories.py`, `cinema/factories.py`, `payments/factories.py`.

**Konwencja nazewnicza:**
- Bazowa: `<Model>Factory` — `UserFactory`, `MovieFactory`, `BookingFactory`, `StripeEventFactory`.
- Subfactories dla wariantów: `ConfirmedBookingFactory`, `PendingBookingFactory`, `ExpiredPendingBookingFactory`, `PastScreeningFactory`, `UpcomingScreeningFactory`.

**Zasady:**
- Factory **NIGDY nie generuje plików obrazów** (`None` dla `ImageField`); osobny `ImageFactory` wyłącznie w testach uploadu, używa `factory.django.ImageField()`.
- `created_at`/`auto_now_add` — `factory.LazyFunction(timezone.now)` lub `freezegun` w teście (gdy potrzebna kontrola czasu).
- Stripe ID w factories: `cs_test_<uuid>`, `pi_test_<uuid>`, `evt_test_<uuid>` (faker uuid). Testy nigdy nie wołają realnego API Stripe.
- `email` w `UserFactory`: `factory.Sequence(lambda n: f"user{n}@example.com")` — unikamy collision na unique constraint.

---

## 11. Mockowanie Stripe w testach

**Pattern bazowy** (`pytest-mock`):
```python
def test_checkout_creates_booking(mocker, screening):
    mock_session = mocker.patch("stripe.checkout.Session.create")
    mock_session.return_value.id = "cs_test_abc"
    mock_session.return_value.url = "https://checkout.stripe.com/c/cs_test_abc"
    # ... rest of test
```

**Helper fixtures** w `conftest.py` (root projektu):
```python
@pytest.fixture
def stripe_session_dict():
    """Returns a dict mimicking stripe.checkout.Session shape."""
    return {
        "id": "cs_test_abc",
        "url": "https://checkout.stripe.com/c/cs_test_abc",
        "client_reference_id": "1",
        "payment_intent": "pi_test_def",
        ...
    }

@pytest.fixture
def stripe_event_dict(stripe_session_dict):
    """Returns a dict mimicking a Stripe webhook event payload."""
    return {
        "id": "evt_test_xyz",
        "type": "checkout.session.completed",
        "data": {"object": stripe_session_dict},
    }
```

**Test webhook signature** — używamy `stripe.WebhookSignature.verify_header` bezpośrednio z testowym `STRIPE_WEBHOOK_SECRET=whsec_test`; payload + sygnaturę liczymy w teście, nie mockujemy.

---

## 12. Polecenia developerskie (do README)

```bash
# Setup
poetry install && poetry run pre-commit install
docker compose up -d
cp .env.example .env  # uzupełnij Stripe test keys
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py seed_db

# Codzienna praca
poetry run python manage.py runserver
stripe listen --forward-to localhost:8000/webhooks/stripe/  # w drugim terminalu

# Quality gates (lokalnie)
poetry run ruff check . --fix
poetry run ruff format .
poetry run mypy .
poetry run pytest --cov

# i18n
poetry run python manage.py makemessages -l en -l pl --ignore=venv
poetry run python manage.py compilemessages
```

---

## 13. Co powstaje w M1 — checklist plików

W trakcie M1 user tworzy następujące pliki kopiując z tego dokumentu:

| US | Plik | Sekcja źródłowa |
|---|---|---|
| US-01 | `pyproject.toml` (deps + project meta) | §1 |
| US-01 | `.env.example` | §9 |
| US-01 | `settings/base.py`, `settings/dev.py`, `settings/prod.py` | (struktura — `KinoMania_wymagania_funkcjonalne.md` §8) |
| US-02 | `docker-compose.yml` | §8 |
| US-03 | `pyproject.toml` (sekcje `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.coverage.*]`) | §2, §3, §4, §5 |
| US-03 | `conftest.py` | §11 (po US-18 doda Stripe fixtures) |
| US-04 | `.pre-commit-config.yaml` | §6 |
| US-05 | `.github/workflows/ci.yml` | §7 |

> Configi to copy-paste — to nie jest „nauka pisania configów". Edukacyjna wartość M1 leży w US-06 (custom User model), US-07 (auth flow), US-08 (seed_db), US-09 (templates).