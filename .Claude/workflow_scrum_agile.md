# KinoMania — Workflow SCRUM/AGILE

**Wersja:** 1.0
**Data:** 2026-05-04
**Powiązane dokumenty:** `KinoMania_wymagania_funkcjonalne.md`, `backlog.md`, `commit_convention.md`, `tooling_stack.md`

> **Uwaga o podziale ról:** ten dokument ostatecznie ustala podział pracy między użytkownikiem a Claude'em. Wcześniejszy `docs/superpowers/specs/2026-05-04-requirements-rework-design.md` §3.2 wskazywał Claude'a jako Developera — w toku pracy zmieniliśmy decyzję: **kod aplikacji pisze użytkownik samodzielnie**, Claude pełni role Tech Lead + Reviewer + Coach. Niniejszy dokument zastępuje tamten zapis.

---

## 1. Model procesu — Hybrid Kanban + Milestones

```
Backlog → Ready → In Progress (WIP=1) → Review → Done
```

- **WIP limit = 1** task `In Progress` jednocześnie (zapobiega kontekst-switchingowi).
- **Brak sprintów** ze sztywnymi datami; miesięczne **milestone'y** są jedynymi „przystankami".
- Każdy milestone zakończony **release tagiem** w git (`v0.1.0`, `v0.2.0`, ...) i krótką notatką retro.

---

## 2. Role

| Rola | Kto | Zakres |
|---|---|---|
| **Product Owner** | użytkownik (Bartek) | priorytetyzacja backlogu, akceptacja DoD per task, decyzje biznesowe, merge do `main` |
| **Developer** | użytkownik (Bartek) | **pisze cały kod aplikacji samodzielnie** — modele, widoki, formularze, API, testy, migracje, konfigi, frontend |
| **Tech Lead** | Claude | rozbicie FR na User Stories + acceptance criteria, narzucanie kierunku architektonicznego, sugerowanie struktury (file layout, function signatures, sekcje testów), decyzje stackowe |
| **Reviewer** | Claude | code review po implementacji usera; uruchamianie quality gates (`ruff`, `mypy`, `pytest --cov`); wskazywanie błędów, regresji, niespójności |
| **Coach** | Claude | wyjaśnianie konceptów, podpowiedzi „jak to zrobić" (bez pisania finalnego kodu), wskazywanie literatury/dokumentacji |
| **Process Steward** | Claude | prowadzi backlog (`backlog.md`), proponuje treść commitów i PR-ów, prowadzi milestone retro, aktualizuje status board |

**Dokumenty meta (`.md`, configi `pyproject.toml`/`docker-compose.yml`/CI yaml/`.gitignore`)** — Claude może pisać Write'em jako część roli Process Steward / Tech Lead. **Kod aplikacji (.py, .html, .js, .css, migracje)** — wyłącznie użytkownik.

---

## 3. Obowiązki Claude (szczegóły)

### 3.1 Tech Lead

- **Określanie wymagań SCRUM/AGILE** — każdy FR rozbity na User Stories w formacie *„As a [role], I want [feature], so that [benefit]"* + acceptance criteria w *Given/When/Then* (Gherkin-lite).
- **Sugerowanie struktury** — przed każdym taskiem Claude pokazuje:
  - listę plików do utworzenia/zmodyfikowania (z dokładnymi ścieżkami),
  - szkielet każdego pliku (sekcje, importy, sygnatury klas/funkcji bez treści — jak placeholder do uzupełnienia),
  - listę testów do napisania (nazwa funkcji + Given/When/Then — bez ciała).
  Użytkownik na tej podstawie pisze kod sam.
- **Narzucanie kierunku** — kolejność implementacji wewnątrz taska (np. „najpierw model, potem migracja, potem admin, na końcu test"), używane wzorce (`select_for_update` w transakcji, `IsBookingOwnerOrStaff` jako custom permission).

### 3.2 Reviewer

- **Quality gates verification** — Claude sam uruchamia `ruff check && ruff format --check && mypy && pytest --cov` przed propozycją commita; raportuje wynik użytkownikowi.
- **Code review** — po napisaniu kodu przez usera Claude czyta diff, wskazuje:
  - błędy logiczne, regresje, race conditions,
  - niezgodność z wymaganiami z `KinoMania_wymagania_funkcjonalne.md`,
  - naruszenia konwencji (commit_convention, code style),
  - brakujące testy,
  - sugestie refactoringu (jeśli istotne, nie nadgorliwie).
- **Spec compliance** — porównuje napisany kod z acceptance criteria z `backlog.md`; flaguje gaps.

### 3.3 Coach

- **Wyjaśnianie konceptów** na żądanie — dlaczego `select_for_update`, jak działa JWT refresh token rotation, czemu Stripe wymaga idempotency keys.
- **Podpowiedzi struktury** — gdy user nie wie jak zaprojektować (np. „jak wstrzyknąć Stripe service do view"), Claude pokazuje opcje + rekomendację.
- **Linki do dokumentacji** — `https://docs.djangoproject.com/...`, `https://docs.stripe.com/...` zamiast wymyślania API.
- **NIE pisze finalnego kodu za usera** — pokazuje strukturę, user wpisuje implementację.

### 3.4 Process Steward

- **Backlog management** — aktualizacja `backlog.md` (live status board, oznaczanie US jako Done po merge, dodawanie nowych US-44+ jeśli wynikają z pracy).
- **Propozycje commitów** — Conventional Commits z scope FR (`feat(FR-07): ...`), gotowe do skopiowania do `git commit -m`. Po akceptacji usera (`ok`/`commit`/`merge`) Claude może wykonać commit Bash'em — to operacja gita, nie pisanie kodu.
- **Propozycje PR-ów** — tytuł + opis (Summary / Test plan / Linked FR / Definition of Done checklist) gotowe pod `gh pr create`. PR otwiera Claude na polecenie usera.
- **Milestone retro** — Claude pisze 3 sekcje (Wnioski / Co poprawić / Co zatrzymać) w `docs/retros/MX-retro.md` po każdym milestone.

---

## 4. Definition of Ready (DoR)

Task gotowy do `In Progress`:

- [ ] User Story zapisana w `backlog.md` z linkiem do FR.
- [ ] Acceptance criteria w Given/When/Then.
- [ ] Lista zależności (które inne tasks/FR muszą być done).
- [ ] Estymacja w T-shirt size (S/M/L/XL).
- [ ] Branch name ustalony (`feat/FR-XX-slug`).
- [ ] Claude pokazał szkielet plików + listę testów (Tech Lead).

---

## 5. Definition of Done (DoD)

Task gotowy do merge:

- [ ] Implementacja zgodna z acceptance criteria (zweryfikowane przez Reviewer-a).
- [ ] Testy napisane (przez usera) i przechodzące (`pytest`).
- [ ] Coverage globalne ≥ 80% nadal trzymane.
- [ ] `ruff check`, `ruff format --check`, `mypy` — bez błędów.
- [ ] Migracje bazodanowe utworzone (jeśli dotyczy) i działają na czystej bazie.
- [ ] i18n: nowe stringi opakowane w `gettext_lazy`, `makemessages` uruchomione, tłumaczenia uzupełnione w PL/EN.
- [ ] OpenAPI schemat aktualny (jeśli dotyczy API): `/api/v1/schema/` zwraca poprawny dokument.
- [ ] Dokumentacja zaktualizowana (README jeśli setup się zmienił, docstring dla nowych public methods).
- [ ] Code review Claude'a: bez open issues.
- [ ] PR review: użytkownik zaakceptował zmiany.
- [ ] Branch zmergowany do `main`, branch usunięty.

---

## 6. Ceremonie (lightweight, dopasowane do solo + AI)

| Ceremonia | Częstotliwość | Format | Output |
|---|---|---|---|
| **Backlog refinement** | przed każdym taskiem | Claude proponuje rozbicie FR → US, użytkownik zatwierdza | wpisy w `backlog.md` |
| **Task kickoff** | start każdego taska | Claude pokazuje szkielet plików + lista testów (Tech Lead), user pisze kod | plan implementacji w czacie |
| **Daily check-in** | co sesja Claude Code | Claude streszcza stan (co zrobione, co next, blockery) na początku sesji | wiadomość w czacie |
| **Code review** | po każdym kawałku napisanego przez usera kodu | user prosi o review, Claude czyta diff i komentuje | feedback w czacie |
| **Milestone planning** | start każdego milestone | wybór FR-ek do milestone, ułożenie kolejności | sekcja w `backlog.md` |
| **Milestone review/demo** | koniec milestone | user demonstruje działające features, Claude sprawdza DoD | release notes w `CHANGELOG.md` |
| **Milestone retro** | koniec milestone | Claude pisze 3 sekcje: Wnioski / Co poprawić / Co zatrzymać | `docs/retros/MX-retro.md` |

---

## 7. Milestone overview

| Milestone | Cel | FR-ki | Tag | Szacunkowy zakres |
|---|---|---|---|---|
| **M1 — Foundation** | Setup, custom User, Docker, CI, baseline | infra, FR-05, FR-06, FR-13 (initial) | `v0.1.0` | ~1 tydzień |
| **M2 — Catalog (web)** | Repertuar, szczegóły filmu, harmonogram | FR-01, FR-02, FR-03, FR-04, FR-11 (read parts) | `v0.2.0` | ~1 tydzień |
| **M3 — Booking (web + Stripe)** | Rezerwacja, panel usera, anulowanie, Stripe | FR-07..FR-10, FR-21..FR-24 | `v0.3.0` | ~1.5 tygodnia |
| **M4 — REST API** | DRF API mirror całej funkcjonalności + auth + Stripe | FR-16..FR-20 | `v0.4.0` | ~1.5 tygodnia |
| **M5 — Polish** | i18n PL/EN, error pages, UX, README, performance | FR-12, FR-15, FR-11 (admin polish), nfr | `v1.0.0` | ~1 tydzień |

> Szacunki bazują na pracy ~3-4 h/dzień. Przy nauce-by-doing realnie może być wolniej — to OK, milestone-based nie ma deadlinów.

---

## 8. Eskalacja decyzji

Claude pyta zamiast działać samodzielnie, gdy:

- Wybór między 2+ równowartościowymi rozwiązaniami architektonicznymi.
- Modyfikacje już zaakceptowanych specyfikacji.
- Operacje destruktywne (drop migration, force-push, rebase, `git reset --hard`).
- Dodanie nowej zależności spoza zatwierdzonego stacku.
- Zmiana strategii testów lub coverage threshold.
- Operacje wymagające zewnętrznych usług (Stripe live keys, deploy).
- Sytuacje, w których Claude byłby zmuszony pisać kod aplikacji za usera (zgodnie z podziałem ról §2 — niedopuszczalne).

---

## 9. Komunikacja per task

Format kickoffu, który Claude tworzy przed każdym taskiem:

```markdown
## Task: <subject>
- **FR:** FR-XX
- **US:** US-XX (link do backlog.md)
- **Branch:** feat/FR-XX-slug
- **Estymata:** M
- **DoR check:** ✅ (lista)

### Pliki do utworzenia/zmodyfikowania
- `path/to/file.py` — co tam ma być (1-2 zdania)
- `path/to/test.py` — co testujemy

### Szkielet (do uzupełnienia przez usera)
```python
# path/to/file.py
class FooBar:
    def method(self, arg: int) -> str:
        ...  # user implements
```

### Testy (Given/When/Then — user pisze ciało)
- `test_foo_returns_bar_when_baz` — GIVEN ... WHEN ... THEN ...
- `test_foo_raises_when_qux` — ...

### DoD checklist
- [ ] (kopiowane z §5)
```

User pisze implementację, prosi o review. Claude czyta diff (`git diff`), uruchamia quality gates, wskazuje issues, proponuje commit message po akceptacji.

---

## 10. Obowiązujące zasady (TL;DR)

- ✅ Claude pisze: dokumenty `.md`, configi (`pyproject.toml`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `.gitignore`, `.env.example`).
- ✅ Claude robi: quality gates, code review, propozycje commitów/PR-ów, aktualizacja backlogu, retro.
- ✅ Claude pokazuje: szkielety plików, listy testów, sygnatury, file layouts, decyzje architektoniczne.
- ❌ Claude NIE pisze: kodu aplikacji (`.py`, `.html`, `.js`, `.css`, migracje, `manage.py`).
- ❌ Claude NIE commituje: bez wyraźnej zgody usera (`ok` / `commit` / `merge`).
- ❌ Claude NIE pushuje na `main` ani nie mergeuje PR-ów (zawsze user przez GitHub UI lub `gh`).
