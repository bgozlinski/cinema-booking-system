# KinoMania — Commit & PR Convention

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązane dokumenty:** `workflow_scrum_agile.md`, `backlog.md`

> **Rola Claude'a:** quality gates + propozycja commit message (jako blok do skopiowania) + (po akceptacji usera) **user samodzielnie wkleja i uruchamia** `git commit` w terminalu. Claude **nie wywołuje** komend `git` Bashem. Kod aplikacji pisze user — Claude reviewuje już-napisany kod i podpowiada komendy. Pełne reguły w `workflow_scrum_agile.md` §2-3.

---

## 1. Format commit message

```
<type>(<scope>): <subject>

[body — opcjonalny, why a nie what]

[footer — opcjonalny: BREAKING CHANGE, Refs, Co-Authored-By]
```

**Wymagania mechaniczne:**
- `<subject>` w trybie rozkazującym, **angielski**, bez kropki na końcu, max 72 znaki w pierwszej linii.
- `<scope>` = numer FR (`FR-07`) **lub** kategoria (`infra`, `ci`, `deps`, `docs`).
- Pusta linia między subject a body.
- Linie body wrap'owane na 100 znaków.
- Footer: `Refs: US-20`, `BREAKING CHANGE: ...`.

---

## 2. Allowed `<type>` (Conventional Commits)

| type | Kiedy używać | Przykład |
|---|---|---|
| `feat` | Nowa funkcjonalność widoczna dla usera | `feat(FR-07): add booking creation flow` |
| `fix` | Bugfix | `fix(FR-22): handle duplicate Stripe events idempotently` |
| `test` | Tylko zmiany w testach (gdy nie towarzyszą `feat`/`fix`) | `test(FR-18): add API contract tests for bookings` |
| `refactor` | Zmiana struktury bez zmiany zachowania | `refactor(FR-09): extract booking-list query to manager` |
| `docs` | Dokumentacja (README, docstrings, komentarze, wymagania) | `docs(infra): document Stripe CLI setup in README` |
| `chore` | Setup, deps, formatowanie, configi (nie kod aplikacji) | `chore(deps): bump djangorestframework to 3.16` |
| `ci` | Tylko zmiany w CI/CD | `ci(infra): cache Poetry deps in GitHub Actions` |
| `style` | Tylko whitespace/format (rzadko, ruff załatwia) | `style: apply ruff format` |
| `perf` | Optymalizacja wydajności | `perf(FR-01): prefetch genres in MovieList` |
| `build` | Zmiany w build systemie / pyproject.toml | `build: switch psycopg to binary extras` |
| `revert` | Cofnięcie poprzedniego commita | `revert: feat(FR-19): admin write API` |

---

## 3. Konwencja `<scope>`

| Scope | Kiedy |
|---|---|
| `FR-XX` | Praca związana z konkretnym FR (większość commitów) |
| `infra` | Setup projektu, Docker, Poetry, struktura katalogów |
| `ci` | GitHub Actions, pre-commit |
| `deps` | Tylko bumping/dodawanie zależności |
| `docs` | Bez kodu — README, .Claude/, retros |
| `i18n` | Tłumaczenia (locale/*.po) — używać przy M5 |
| `M1`–`M5` | Tylko gdy commit dotyczy całego milestone (rzadko, np. tag/release notes) |

**Multiscope:** dopuszczalne `feat(FR-21,FR-22): ...` gdy zmiana atomicznie obejmuje 2 FR (np. Stripe Checkout + webhook idą razem).

---

## 4. Przykłady (full template, pod kopiuj-wklej)

**Czysty `feat`:**
```
feat(FR-07): implement booking creation with row locking

Wraps Booking creation in transaction.atomic() with select_for_update
on the Screening row to prevent race conditions when two users compete
for the last seats. Returns 409 Conflict when capacity check fails
post-lock (defensive — lock should prevent it but the check stays).

Refs: US-20
```

**`feat` + nowy model:**
```
feat(FR-22): add StripeEvent model for webhook idempotency

Stores every received Stripe event_id with received_at and payload.
Webhook handler rejects duplicates by event_id unique constraint, so
retries from Stripe never double-process state changes.

Refs: US-25
```

**`fix` z BREAKING:**
```
fix(FR-18): rename booking API field seats -> seats_count

Aligns API serializer with the model field name. Existing API clients
must update their request/response payloads.

BREAKING CHANGE: POST /api/v1/bookings/ now expects "seats_count"
instead of "seats". GET responses also use the new key.

Refs: US-32
```

**`test`-only (gdy testy dochodzą po fakcie):**
```
test(FR-22): add idempotency test for duplicate Stripe events

Sends the same checkout.session.completed event twice and asserts
the booking transitions to CONFIRMED only once.

Refs: US-25
```

**`chore` + `deps`:**
```
chore(deps): add stripe and djangorestframework-simplejwt

Pinned to ^11.0 and ^5.3 respectively. Bundles djangorestframework-stubs
in dev group for mypy.

Refs: US-29
```

**`docs` (bez kodu aplikacji):**
```
docs(infra): document local Stripe webhook setup with stripe CLI

Adds "Local development with Stripe" section to README explaining
stripe listen --forward-to and where to copy the whsec_ secret to .env.
```

---

## 5. Reguła „jeden commit = jedna spójna zmiana"

**Jeden commit = jedna spójna zmiana:**
- ✅ Model + migracja + admin dla tego modelu w jednym commicie.
- ✅ View + template + URL routing + test dla tego view w jednym commicie.
- ❌ Wiele niezwiązanych refactorów w jednym commicie (split).
- ❌ Mieszanie `feat` z `chore(deps)` w jednym (split).

**Reguła:** „commit message musi się zmieścić w jednym `<type>(<scope>):`". Jeśli trzeba dwóch typów — zrób dwa commity.

**Wyjątek:** `feat` + odpowiadające testy idą razem (zgodnie z TDD-2 — testy są częścią kompletnej funkcjonalności).

---

## 6. Co Claude robi w ramach commita

> **Rola Claude'a w cyklu commita:** verifikacja + propozycja treści message i komendy `git commit`. **User samodzielnie** uruchamia komendy `git` w terminalu. **Kod aplikacji** napisany przez usera **przed** rozpoczęciem cyklu commita.

**Przed każdym commitem:**
1. **User** ogłasza „skończyłem implementację" / „zrób review" / „commitujemy".
2. **Claude** czyta diff przez `Read`/`Grep` na zmienionych plikach (NIE używa `git diff` — wszystkie git ops po stronie usera).
3. **Claude** uruchamia quality gates lokalnie (te są w gestii Claude'a):
   - `poetry run ruff check .`
   - `poetry run ruff format --check .`
   - `poetry run mypy .`
   - `poetry run pytest --cov`
4. **Claude** raportuje wynik wszystkich gates użytkownikowi (zielone / błędy + linie).
5. Jeśli błędy — **Claude** wskazuje co poprawić; user poprawia; wracamy do kroku 2.
6. Gdy zielone — **Claude** pokazuje proponowany commit message w bloku do skopiowania (HEREDOC bezpieczny dla bash i PowerShell, gdy jest tylko 1 linia używamy `git commit -m "..."`):

```bash
git add <pliki>
git commit -m "$(cat <<'EOF'
feat(FR-07): implement booking creation with row locking

<body>

Refs: US-20

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

7. **User** kopiuje blok, wkleja do terminala, wykonuje. Akceptacja jest implicite (skoro user uruchamia, zgadza się).
8. **Claude** sprawdza wynik (np. user wkleja output, lub Claude czyta `.git/HEAD` przez Read jeśli musi potwierdzić).
9. Po commicie **Claude** aktualizuje `backlog.md` (status board: US → Done jeśli ukończony) i sprawdza czy zostały jakieś gaps względem AC.

**Komendy git które Claude proponuje (nie uruchamia):**
- `git add <pliki>` (zawsze konkretne ścieżki, nigdy `-A`/`.`)
- `git commit -m "..."` (z HEREDOC dla wieloliniowych)
- `git checkout -b feat/FR-XX-slug`
- `git push -u origin feat/FR-XX-slug`
- `git push` (po pierwszym push z `-u`)
- `git tag -a v0.X.0 -m "MX: description"` + `git push --tags`
- `gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"`

---

## 7. PR template (`.github/pull_request_template.md`)

```markdown
## Summary
<1–3 bullety: co i dlaczego>

## Linked
- FR: FR-XX
- US: US-XX

## Definition of Done checklist
- [ ] Acceptance Criteria spełnione
- [ ] Testy napisane i przechodzące (`pytest`)
- [ ] Coverage ≥ 80%
- [ ] `ruff check`, `ruff format --check`, `mypy` — czyste
- [ ] Migracje OK na czystej bazie
- [ ] i18n: `gettext_lazy` na nowych stringach, `makemessages` uruchomione
- [ ] OpenAPI schema aktualny (jeśli dotyczy API)
- [ ] README zaktualizowane (jeśli setup się zmienił)

## Test plan
- [ ] <ręczny test 1>
- [ ] <ręczny test 2>

## Screenshots / API examples
<dla zmian UI lub API>

## Notes
<otwarte pytania, follow-upy, znane ograniczenia>
```

---

## 8. PR title

**Identyczny format jak commit message:** `<type>(<scope>): <subject>`.

Np. PR tytułowy do US-20:
```
feat(FR-07): implement booking creation with row locking
```

**Powód:** używamy GitHub *Squash & merge* (zalecane dla feature branchy w GitHub Flow + release branche). Tytuł PR staje się message squashed commita — i wtedy historia `main` ma jednolity Conventional Commits format.

---

## 9. Branche → tagowanie (release flow)

**Branch naming (przypomnienie z `backlog.md` §6):**
- `feat/FR-XX-<slug>` — feature branche
- `fix/FR-XX-<slug>` — bugfix branche
- `chore/M1-<slug>`, `ci/M1-<slug>`, `perf/...`, `docs/...` — pozostałe
- `release/M1`, `release/M2`, ... — release branche per milestone

**Release flow per milestone:**
1. Wszystkie US z milestone zmergowane do `main` (przez PR + squash).
2. `git checkout -b release/M3` z `main`.
3. Bump wersji w `pyproject.toml` (`version = "0.3.0"`).
4. Wpis w `CHANGELOG.md` (Claude proponuje treść z commitów milestone'a, user akceptuje).
5. PR `release/M3 → main`, merge.
6. Tag: `git tag -a v0.3.0 -m "M3: Booking + Stripe"` + `git push --tags`.
7. Notatka retro w `docs/retros/M3-retro.md` (Claude pisze 3 sekcje: Wnioski / Co poprawić / Co zatrzymać).

---

## 10. Operacje wymagające ręcznej akceptacji

Claude NIE wykonuje samodzielnie:

- **Wszystkie komendy `git` i `gh`** (z definicji roli — user uruchamia każdą z nich sam, Claude tylko proponuje treść).
- Cokolwiek dotykającego sekretów (`.env`, klucze, hasła w czacie) — Claude flaguje, user wprowadza ręcznie.
- Force-push, rebase na `main`, `git reset --hard` — destruktywne, zawsze flaguje przed propozycją.
- Merge do `main` (zawsze przez PR, zawsze user klika *Squash & merge* na GitHubie).
- Zmiana migracji która już wygenerowała plik (nowa migracja zamiast edytować istniejącą).
- Tag releasowy — Claude przygotowuje komendę, user uruchamia.
- **Pisanie kodu aplikacji** (`.py`, `.html`, `.js`, `.css`, migracje) — z definicji roli (`workflow_scrum_agile.md` §2). Claude pokazuje strukturę, user pisze.