# Design — KinoMania: `seed_db` initial (US-08 / FR-13, M1 scope)

**Data:** 2026-05-19
**Status:** Approved (pending final user review of this written spec)
**Autor:** brainstorming session — bartek + Claude (Opus 4.7)
**Powiązany US:** US-08 (`feat/FR-13-seed-db-initial`) — scope zwężony względem backloga
**Powiązany FR:** FR-13 (Komenda management `seed_db`) — M1 wersja initial; rozszerzenia w US-16 (M2) i US-18+ (M3)
**Cel:** Specyfikacja komendy `python manage.py seed_db` w wersji M1: zasiewa wyłącznie userów (8 active + 2 inactive z deterministycznymi emailami) do manualnego smoke testingu auth flow z US-07. Genres/Halls/Movies/Screenings/Bookings dochodzą w kolejnych milestone'ach. Dokument NIE zawiera planu implementacyjnego — ten powstanie przez `superpowers:writing-plans` po akceptacji specu.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura i lokalizacja](#2-architektura-i-lokalizacja)
3. [Interfejs CLI](#3-interfejs-cli)
4. [Specyfikacja danych](#4-specyfikacja-danych)
5. [Bezpieczeństwo, errory, guardy](#5-bezpieczeństwo-errory-guardy)
6. [Strategia testów](#6-strategia-testów)
7. [Zmiany w plikach](#7-zmiany-w-plikach)
8. [Aktualizacje dokumentacji](#8-aktualizacje-dokumentacji)
9. [Plan commitów](#9-plan-commitów)
10. [Out of scope (follow-up)](#10-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Scope US-08 wobec brakujących modeli Genre/Hall** | Zwężamy US-08 do *tylko Users* (Genre/Hall nie istnieją jako modele do US-10). Genres + Halls przesuwamy do US-16 (M2) razem z Movies/Screenings. Wymaga edytu backloga (US-08 AC, US-16 scope). |
| Q2 | **Lokalizacja komendy** | `apps/cinema/management/commands/seed_db.py`. Tworzymy minimalny szkielet `apps/cinema/` (apps.py, migrations/__init__.py — brak modeli) zgodnie ze spec FR-13. US-10 naturalnie rozszerza tę app. |
| Q3 | **Skład 10 userów** | 8 active + 2 inactive. Inactive accounts udostępniają surface do manualnego testowania `/accounts/activate/resend/` i wygasłych linków (US-07 flow). |
| Q4 | **Zachowanie na non-empty DB bez flag** | Fail-loud — `CommandError` z czytelną instrukcją. Plus `--append` flag dla idempotent dodawania brakujących userów (świadomy wybór per wywołanie, brak cichego dual-trybu). |
| Q5 | **Generowanie userów** | Inline `Faker("pl_PL")` w komendzie (production code). NIE reuse `UserFactory` z `tests/accounts/factories.py` — production kod nie powinien importować z `tests/`. |

---

## 2. Architektura i lokalizacja

### 2.1 Wysokopoziomowy flow

```
$ poetry run python manage.py seed_db [--flush|--append] [--force] [--users N]
           │
           ▼
  [guard 1] DEBUG check ──no, no --force──> CommandError("disabled")
           │
  [guard 2] mutex --flush/--append ──both──> CommandError("mutually exclusive")
           │
  [guard 3] non-empty DB ──data + no flag──> CommandError("not empty; use --flush/--append")
           │                                            (--flush: delete non-supers)
           │                                            (--append: skip-existing in loop)
           ▼
  transaction.atomic():
     for i in 1..N:
        email = f"seed.user{i}@kinomania.local"
        first/last_name = Faker("pl_PL")
        is_active = (i <= ceil(N * 0.8))
        user.set_password(SEED_DB_DEFAULT_PASSWORD)
        user.save()
           │
           ▼
  stdout: "Seeded N users (A active, I inactive). Inactive: ..."
```

### 2.2 Struktura plików (nowe)

```
apps/cinema/
├── __init__.py                       # empty
├── apps.py                           # CinemaConfig(name="apps.cinema", default_auto_field=BigAutoField)
├── migrations/
│   └── __init__.py                   # empty — modele dojdą w US-10
└── management/
    ├── __init__.py
    └── commands/
        ├── __init__.py
        └── seed_db.py                # główna logika (FR-13, M1)

tests/cinema/
├── __init__.py
└── test_seed_db.py                   # Claude pisze (role-division)
```

### 2.3 Zmiany w istniejących plikach

| Plik | Zmiana |
|---|---|
| `settings/base.py` | `INSTALLED_APPS += ["apps.cinema"]` (po `"apps.accounts"`) + nowa zmienna `SEED_DB_DEFAULT_PASSWORD = env.str("SEED_DB_DEFAULT_PASSWORD", default="test1234")` |
| `.env.example` | dodać linię `# SEED_DB_DEFAULT_PASSWORD=test1234` (opcjonalna override, komentarz) |
| `pyproject.toml` | **bez zmian** — `faker (>=40.15.0,<41.0.0)` już jest w `[dependency-groups] dev` (zweryfikowane). Django lazy-loaduje moduły management commands, więc `apps/cinema/management/commands/seed_db.py` nie próbuje importować `Faker` w prod env (komenda nigdy tam nie jest wywoływana). |

---

## 3. Interfejs CLI

### 3.1 Sygnatura

```
poetry run python manage.py seed_db [--flush | --append] [--force] [--users N]
```

### 3.2 Flagi

| Flag | Typ | Default | Semantyka |
|---|---|---|---|
| `--flush` | `store_true` | `False` | Usuwa wszystkich userów z `is_superuser=False`, potem tworzy seed. Mutually exclusive z `--append`. |
| `--append` | `store_true` | `False` | Idempotent: tworzy tylko userów, których email nie istnieje. Info do stdout dla skipped. Mutually exclusive z `--flush`. |
| `--force` | `store_true` | `False` | Bypass guardu `DEBUG=False`. Drukuje warning na stderr. Ortogonalne do `--flush`/`--append`. |
| `--users N` | `int` | `10` | Liczba seedowanych userów. Active count = `floor(N*0.8)`, inactive = `N - active`. Wymaga `N >= 1`. |

### 3.3 Exit codes

| Code | Kiedy |
|---|---|
| `0` | Success |
| `1` | `CommandError` (DEBUG guard, mutex, non-empty bez flag, `--users < 1`) |
| `2` | argparse error (np. `--users` non-integer) — Django default |

### 3.4 Przykładowy stdout (happy path)

```
$ poetry run python manage.py seed_db
Seeded 10 users (8 active, 2 inactive). Default password: test1234.
Inactive accounts:
  seed.user9@kinomania.local
  seed.user10@kinomania.local
```

### 3.5 Przykładowy stdout (`--append`)

```
$ poetry run python manage.py seed_db --append
Skipping existing: seed.user1@kinomania.local
Skipping existing: seed.user2@kinomania.local
Appended 8 users (2 skipped). Default password: test1234.
```

### 3.6 Przykładowy stderr (`--force` w `DEBUG=False`)

```
WARNING: Running seed_db in non-DEBUG environment. This is intended for dev only.
```

---

## 4. Specyfikacja danych

### 4.1 Domyślny seed (N=10)

| Pole | Wartość |
|---|---|
| **Liczba userów** | 10 |
| **Active / inactive split** | 8 active (`is_active=True`) + 2 inactive (`is_active=False`) |
| **`is_staff`** | `False` (zawsze) |
| **`is_superuser`** | `False` (zawsze) |
| **`email`** | `seed.user{i}@kinomania.local` dla `i ∈ 1..10` (deterministyczne, sekwencyjne) |
| **`first_name`** | `Faker("pl_PL").first_name()` — random przy każdym wywołaniu |
| **`last_name`** | `Faker("pl_PL").last_name()` — random przy każdym wywołaniu |
| **`password`** | `settings.SEED_DB_DEFAULT_PASSWORD` (default `test1234`), zapisane przez `user.set_password()` → PBKDF2 |

### 4.2 Mapowanie active/inactive na indeksy

Deterministyczne — userów 1..8 = active, 9..10 = inactive. Pozwala test asercjom polegać na konkretnym indeksie bez sprawdzania wszystkich userów.

### 4.3 Skalowanie dla `--users N`

```
active_count   = floor(N * 0.8)
inactive_count = N - active_count
```

| N | active | inactive |
|---|---|---|
| 1 | 0 | 1 |
| 5 | 4 | 1 |
| 10 | 8 | 2 |
| 20 | 16 | 4 |

Edge case `N=1` → 0 active + 1 inactive (akceptowalne; user świadomie żąda `--users 1`).

### 4.4 Co NIE jest seedowane (US-08)

- ❌ Genres, Halls — modele dojdą w US-10; seed w US-16
- ❌ Movies, Actors, Directors, Screenings — US-10 / US-16
- ❌ Bookings, StripeEvent — US-18+ (M3)
- ❌ Superuser — tworzony manualnie przez `createsuperuser` (decyzja świadoma — superuser to prod-grade account, nie powinien lecieć z seedu)

---

## 5. Bezpieczeństwo, errory, guardy

### 5.1 Production guard (`DEBUG=False`)

| Scenariusz | Wynik |
|---|---|
| `DEBUG=True`, brak `--force` | OK, proceed |
| `DEBUG=False`, brak `--force` | `CommandError("seed_db is disabled when DEBUG=False. Use --force to override (DEV ONLY).")` → exit 1 |
| `DEBUG=False`, `--force` | Warning na stderr, proceed |

### 5.2 Mutually-exclusive flags

| Combo | Wynik |
|---|---|
| `--flush --append` | `CommandError("--flush and --append are mutually exclusive")` → exit 1 |

### 5.3 Non-empty DB guard

| Stan DB | Flag | Wynik |
|---|---|---|
| `non_super_count == 0` | (any/none) | proceed (czysty create) |
| `non_super_count > 0` | brak `--flush` i `--append` | `CommandError("Database not empty (found {N} non-superuser user(s)). Use --flush to wipe non-superusers or --append to add only missing.")` → exit 1 |
| `non_super_count > 0` | `--flush` | `User.objects.filter(is_superuser=False).delete()` w transakcji, potem create. Superuserzy zostają. |
| `non_super_count > 0` | `--append` | Loop: `User.objects.get_or_create(email=...)`; istniejący → skip + info; brakujący → create. Summary `"Appended K new users (M skipped)"` |

### 5.4 Walidacja inputów

| Input | Wynik |
|---|---|
| `--users 0` lub ujemny | `CommandError("--users must be >= 1")` |
| `--users` non-integer | argparse error (exit 2) |

### 5.5 Atomicity

Cała sekcja seedu (po przejściu guardów) jest w `transaction.atomic()`. Obejmuje:
- delete non-supers (jeśli `--flush`)
- pętla create userów

Failure w środku pętli → rollback wszystkiego (włącznie z flushem). Brak częściowych stanów.

### 5.6 Co świadomie NIE obsługujemy (YAGNI)

- ❌ Email collision z non-seed userem (user zarejestrowany przez `/register/` jako `seed.user5@kinomania.local`) — non-empty guard złapie default flow; `--append` skip-uje; `--flush` usuwa (świadoma destrukcja).
- ❌ Race conditions — single-shot dev command.
- ❌ i18n stringów stdout — dev tool, EN ok.
- ❌ Batch insert / `bulk_create` — 10 userów to <1s; `set_password()` per user wymaga osobnego save (bulk_create pomija `save()` chain).

---

## 6. Strategia testów

**Lokalizacja:** `tests/cinema/test_seed_db.py` (Claude writes, per `feedback_role_division`).

**Conventions:**
- `@pytest.mark.django_db` na każdym teście (DB access).
- `from django.core.management import call_command` + `call_command(..., stdout=StringIO(), stderr=StringIO())` do capture (Django command stdout nie jest chwytany przez pytest `capsys`).
- `from django.test import override_settings` do toggle DEBUG.
- `from django.contrib.auth import get_user_model; User = get_user_model()`.

### 6.1 Test inventory (10 testów)

| # | Test | Co weryfikuje |
|---|---|---|
| 1 | `test_seed_db_creates_default_counts` | Pusta DB → `call_command("seed_db")` → `User.objects.count() == 10`, 8 active + 2 inactive |
| 2 | `test_seed_db_emails_are_deterministic` | Asercja: emaile to dokładnie `seed.user1@..` … `seed.user10@..`; inactive na indeksach 9, 10 |
| 3 | `test_seed_db_password_is_hashed` | `user.check_password("test1234") is True` i `user.password.startswith("pbkdf2_")` |
| 4 | `test_seed_db_no_staff_no_super` | Wszystkie `is_staff=False`, `is_superuser=False` |
| 5 | `test_seed_db_blocked_when_debug_false_without_force` | `@override_settings(DEBUG=False)` → rzuca `CommandError` o "disabled"; `User.objects.count() == 0` |
| 6 | `test_seed_db_force_bypasses_production_guard` | `@override_settings(DEBUG=False)` + `--force` → 10 userów, stderr ma "WARNING" |
| 7 | `test_seed_db_flush_and_append_mutually_exclusive` | `--flush --append` razem → `CommandError` o "mutually exclusive" |
| 8 | `test_seed_db_blocks_on_non_empty_db_without_flags` | Pre-existing user → rzuca `CommandError` "Database not empty"; oryginalny user zostaje |
| 9 | `test_seed_db_flush_preserves_superuser_wipes_others` | superuser + 2 non-supers → `--flush` → superuser nadal istnieje, 2 oryginalni usunięci, 10 nowych seedowych |
| 10 | `test_seed_db_append_idempotent_skip_existing` | Pre-seed 3 userów `seed.user1..3@..` → `--append` → total 10 (3 skipped + 7 nowych); pierwsze 3 zachowują oryginalny `date_joined` |

### 6.2 Czego świadomie NIE testujemy

- ❌ Konkretnych imion z Faker (random, flaky).
- ❌ Locale Faker (`pl_PL` vs `en_US`) — dev convenience, nie kontrakt.
- ❌ Atomicity przy partial failure (monkeypatch `User.save()` to over-engineering dla M1; `transaction.atomic()` to Django builtin).
- ❌ Performance — 10 userów <1s, brak optymalizacji do testowania.

### 6.3 Coverage target

`apps/cinema/management/commands/seed_db.py` ≥ 90% (krytyczny dev tool, mało branchingu). Globalny `--cov-fail-under=80` pozostaje spełniony.

---

## 7. Zmiany w plikach

### 7.1 Nowe pliki

| Plik | Cel | Autor |
|---|---|---|
| `apps/cinema/__init__.py` | empty | user |
| `apps/cinema/apps.py` | `CinemaConfig(name="apps.cinema")` | user |
| `apps/cinema/migrations/__init__.py` | empty | user |
| `apps/cinema/management/__init__.py` | empty | user |
| `apps/cinema/management/commands/__init__.py` | empty | user |
| `apps/cinema/management/commands/seed_db.py` | główna logika komendy | user |
| `tests/cinema/__init__.py` | empty | Claude |
| `tests/cinema/test_seed_db.py` | 10 testów per §6.1 | Claude |

### 7.2 Modyfikowane pliki

| Plik | Zmiana | Autor |
|---|---|---|
| `settings/base.py` | `INSTALLED_APPS += ["apps.cinema"]` + `SEED_DB_DEFAULT_PASSWORD = env.str(...)` | user |
| `.env.example` | komentarz `# SEED_DB_DEFAULT_PASSWORD=test1234` | user |
| `pyproject.toml` / `poetry.lock` | **bez zmian** — faker już w `[dependency-groups] dev` | — |

---

## 8. Aktualizacje dokumentacji

### 8.1 `.Claude/backlog.md`

**US-08 (`§1`, linie ~209-230):**
- AC #1: zmienić z "tworzy 9 genres, 3-5 halls, 10 users z hasłem test1234" → "tworzy 10 users (8 active + 2 inactive) z hasłem test1234, emaile `seed.user{i}@kinomania.local`"
- AC #2: zmienić z "--flush czyści w odpowiedniej kolejności (zachowując superusery)" → "--flush usuwa wszystkich non-superuser users (zachowując superusery)"
- Dodać AC #5: "GIVEN --append na non-empty DB WHEN istnieją niektóre seed userzy THEN brakujący są tworzeni, istniejący skip z info"
- Dodać AC #6: "GIVEN --flush --append razem THEN CommandError"
- **Tests-first** — zaktualizować listę testów per §6.1 (10 testów), zmienić ścieżkę `cinema/tests/test_seed_db.py` → `tests/cinema/test_seed_db.py`.
- **DoR:** wszystkie 4 checkboxy → `[✅]`.
- Dopisać linki do `**Spec:** [...](../docs/superpowers/specs/2026-05-19-seed-db-initial-design.md)` i (po planie) `**Plan:** [...]`.

**US-16 (`§2`, tabela M2):**
- Tytuł: `Rozbudowa seed_db — Movies, Screenings` → `Rozbudowa seed_db — Genres, Halls, Movies, Screenings`
- Estymata: `S` → `M`
- Branch bez zmian: `feat/FR-13-seed-db-movies`.

**Status board (`§7`):**
- US-08 → kolumna **In Progress (WIP=1)** (po starcie implementacji).

### 8.2 `.Claude/KinoMania_wymagania_funkcjonalne.md`

**§FR-13 (linie ~358-360):**
- Zaktualizować ścieżkę: `cinema/management/commands/seed_db.py` → `apps/cinema/management/commands/seed_db.py` (per decyzja strukturalna 2026-05-18).
- Dodać sub-sekcję "FR-13.M1 (US-08): Users only" z odsyłaczem do tego specu.

### 8.3 Inne docs

Bez zmian w `workflow_scrum_agile.md`, `tooling_stack.md`, `commit_convention.md`.

---

## 9. Plan commitów

Wstępna proponowana sekwencja (finalna lista powstanie w pliku planu po `superpowers:writing-plans`):

1. `docs(infra): scope US-08 to users-only, push genres/halls to US-16` — edyty `.Claude/backlog.md` + `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-13 path + dodanie tego specu.
2. `chore(FR-13): scaffold apps/cinema package (apps.py, migrations, management/)`
3. `feat(FR-13): seed_db base command with DEBUG guard and --force`
4. `feat(FR-13): seed_db creates 10 users (8 active + 2 inactive)`
5. `feat(FR-13): seed_db --flush wipes non-superusers`
6. `feat(FR-13): seed_db --append skips existing users`
7. `feat(FR-13): seed_db --users N flag with active/inactive split`
8. `test(FR-13): comprehensive test suite for seed_db (10 tests)`
9. `docs(FR-13): mark US-08 as Done in backlog status board`

Commity 3-7 mogą być TDD-driven — Claude pisze fail test, user implementuje minimal kod, commit. Decyzja test-by-test vs feature-by-feature zostanie podjęta w planie.

---

## 10. Out of scope (follow-up)

- ❌ Seedowanie Genres + Halls — US-16 (M2), gdy modele istnieją po US-10.
- ❌ Seedowanie Movies, Actors, Directors, Screenings — US-16 (M2).
- ❌ Seedowanie Bookings + 5% PENDING dla testowania `expire_pending_bookings` — US-18+ (M3), per `KinoMania_wymagania_funkcjonalne.md` §828.
- ❌ Faker `seed()` dla deterministycznych imion — nie wymagane, testy asercja tylko na countach/flagach.
- ❌ Bulk insert (`bulk_create`) — `set_password()` per user wymaga osobnego save.
- ❌ i18n stringów stdout/stderr komendy — dev tool, EN.
- ❌ `seed_db --movies=N --bookings=N` flagi z FR-13 — dochodzą wraz z odpowiednimi modelami w M2/M3.

---

**Następny krok:** po akceptacji tego specu — `superpowers:writing-plans` produkuje plan implementacyjny w `docs/superpowers/plans/2026-05-19-seed-db-initial.md` z explicit TDD task list i checkpointami review.
