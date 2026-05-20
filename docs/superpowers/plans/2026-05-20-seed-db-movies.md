# seed_db Extension Implementation Plan (US-16 — FR-13 M2 scope)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Extend `apps/cinema/management/commands/seed_db.py` to also seed `Genre`, `Hall`, `Actor`, `Director`, `Movie`, `Screening` data (in addition to users). Closes US-16. Unblocks manual QA for US-11..US-14 (catalog views) + admin-side smoke testing.

**Architecture:** Single command file grows from ~115 lines to ~250 lines. Per-entity helpers are extracted as private methods on the `Command` class (`_seed_genres`, `_seed_halls`, `_seed_actors`, `_seed_directors`, `_seed_movies`, `_seed_screenings`) so each can be reasoned about and tested in isolation. The single `transaction.atomic()` block covers all creation; `--flush` deletes in dependency-safe order (`Screening` PROTECTs `Hall`, so screenings must die first). Non-empty guard widens to include cinema entities. Photos/posters left blank (Pillow upload out of scope for seed data — admin "—" renders gracefully).

**Tech Stack:** Django 6 `BaseCommand`, `faker` (`pl_PL` locale + en_US fallback for `catch_phrase`), `random` stdlib, `Decimal` for prices, `timezone.now()` + `timedelta` for screening dates, pytest-django `call_command` for integration tests.

**Branch:** `feat/FR-13-seed-db-movies` (per backlog US-16).

---

## Pre-flight checklist (read these first)

- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-13 — seed_db spec source of truth (M2 scope lines ~358-383)
- [ ] `.Claude/m2_planning.md` line 71 — recommended counts (5 genres → spec overrides to 9, 3 halls, 30 movies → spec overrides to 20 default, 200 screenings → spec overrides to 100 default)
- [ ] `apps/cinema/management/commands/seed_db.py` — current M1 users-only impl (115 lines, what we're extending)
- [ ] `tests/cinema/test_seed_db.py` — test pattern template (call_command + DB assertions)
- [ ] `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md` — original US-08 design decisions (still apply: `pl_PL` locale, fail-loud guards, `--flush`/`--append` mutex)
- [ ] `apps/cinema/models.py` — model constraints (Screening.hall is PROTECT; Movie/Screening relations)

---

## Design notes (US-16 scope)

### Final command shape

```
poetry run python manage.py seed_db [--flush] [--append] [--force]
                                    [--users=N] [--movies=N] [--screenings=N]
```

| Flag | Default | Behavior |
|---|---|---|
| `--users=N` | 10 | already supported |
| `--movies=N` | 20 | NEW: number of movies to create |
| `--screenings=N` | 100 | NEW: number of screenings to create |
| `--force` | off | unchanged — bypass DEBUG=False guard |
| `--flush` | off | extended — wipes cinema data (FK-safe order) + non-super users |
| `--append` | off | extended — non-empty guard treats cinema rows as "not empty" too |

**Fixed (non-configurable in US-16):**
- Genres: exactly 9 (fixed list)
- Halls: random 3-5 with capacity 50-200
- Actors: 30 (enough M2M variety for 20 movies × 3-8 actors)
- Directors: 10 (enough M2M variety for 20 movies × 1-2 directors)
- No bookings (US-18+)

### `--append` semantics for cinema (decision)

- **Genres:** skip-if-exists by `name` (fixed list, idempotent).
- **Halls / Actors / Directors / Movies / Screenings:** always create *additional* — no natural unique key to skip on. `--append --movies=5` adds 5 more movies on top of whatever exists.
- **Users:** unchanged (skip-if-exists by email).

This matches the user-side `--append` spirit ("add what's missing or new without erasing"). Documented in the success-output line.

### `--flush` deletion order (FK constraints matter)

```
Screening (PROTECT → Hall)  → must die FIRST
Movie     (CASCADE auto-clears M2M tables)
Hall      (now safe to delete)
Actor     (M2M via Movie already cleared)
Director  (M2M via Movie already cleared)
Genre     (M2M via Movie already cleared)
User      (filter is_superuser=False — unchanged)
```

### Non-empty guard widening

Current: `non_super_count = User.objects.filter(is_superuser=False).count()`.
New: also count `Genre`, `Hall`, `Actor`, `Director`, `Movie`, `Screening`. If **any** > 0 (or non-super users > 0), require `--flush` or `--append`.

### Data generation rules (per FR-13)

| Entity | Method |
|---|---|
| Genre | Fixed list: `["Action", "Comedy", "Drama", "Horror", "Sci-Fi", "Animation", "Thriller", "Romance", "Documentary"]` |
| Hall | name = `"Hall {i}"` (deterministic 1..N); capacity = `random.randint(50, 200)` |
| Actor | full_name = `fake.name()` (pl_PL); biography = `fake.paragraph()`; photo blank |
| Director | full_name = `fake.name()` (pl_PL); biography = `fake.paragraph()`; photo blank |
| Movie | title = `fake.catch_phrase()`; description = `fake.paragraph(nb_sentences=5)`; release_date = `today - timedelta(days=random.randint(0, 730))`; duration_minutes = `random.randint(80, 180)`; poster blank; trailer_url blank; M2M: `random.sample(genres, k=random.randint(1,3))`, `random.sample(actors, k=random.randint(3,8))`, `random.sample(directors, k=random.randint(1,2))` |
| Screening | movie = `random.choice(movies)`; hall = `random.choice(halls)`; start_time = `timezone.now() + timedelta(days=random.randint(-7,30), hours=random.randint(0,23))`; price = `Decimal(f"{random.uniform(25, 55):.2f}")` |

Faker locale: `Faker("pl_PL")` (already in the file). `catch_phrase()` falls back to en_US automatically if pl_PL provider doesn't support it.

No Faker seed — tests assert counts/types/ranges, not specific content.

### Out of scope (deferred)

- Bookings + StripeEvent seeding → US-18+ (M3, FR-13 §M3)
- Photo/poster uploads → keep blank (admin renders "—" already from US-15)
- Progress bar (TQDM) → out of scope; success summary line is enough

---

## File structure

```
apps/cinema/management/commands/seed_db.py     ✎ extended (~115 → ~250 lines)
tests/cinema/test_seed_db.py                   ✎ ~10 new tests
.Claude/backlog.md                             ✎ status board (Task 1 + Task 8)
memory/project_kinomania_bootstrap.md          ✎ after merge — M2 progress (Task 8)
```

No new files. No new deps. No migrations.

---

## Task 1: Branch + backlog DoR

**Files:**
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (user): branch off main**

```bash
git checkout main
git pull
git checkout -b feat/FR-13-seed-db-movies
```

- [ ] **Step 2 (Claude): move US-16 from Ready to In Progress in `.Claude/backlog.md` §7**

- [ ] **Step 3 (user): commit plan + backlog**

```bash
git add docs/superpowers/plans/2026-05-20-seed-db-movies.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-16 + mark in progress"
```

---

## Task 2: Genres (fixed list of 9)

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

**Why first:** Simplest entity (no Faker, no randomness, no relations). Locks in the call_command + count-assertion pattern for all subsequent cinema entities.

- [ ] **Step 1 (Claude): add cinema imports + `TestSeedDbCinema::test_seeds_nine_named_genres` to test file**

Append imports (after existing User import):

```python
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
```

Append at end of file:

```python
EXPECTED_GENRE_NAMES = {
    "Action",
    "Comedy",
    "Drama",
    "Horror",
    "Sci-Fi",
    "Animation",
    "Thriller",
    "Romance",
    "Documentary",
}


@pytest.mark.django_db
def test_seed_db_creates_nine_named_genres():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 9
    assert set(Genre.objects.values_list("name", flat=True)) == EXPECTED_GENRE_NAMES


@pytest.mark.django_db
def test_seed_db_genre_seeding_is_idempotent_on_append():
    # Pre-create 2 of the 9 genres.
    Genre.objects.create(name="Action")
    Genre.objects.create(name="Drama")

    call_command("seed_db", "--append", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 9
    assert set(Genre.objects.values_list("name", flat=True)) == EXPECTED_GENRE_NAMES
```

- [ ] **Step 2 (user): run — expect 2 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_creates_nine_named_genres tests/cinema/test_seed_db.py::test_seed_db_genre_seeding_is_idempotent_on_append -v
```

The append test will probably fail with `CommandError: Database not empty` (because non-empty guard counts users only currently; once we pre-create Genres without users, the guard *might* let through — actually it will. Let me re-check). Actually — with 2 genres but 0 users, `non_super_count == 0`, so guard passes and seeding proceeds. But there's no genre seeding yet → assertion fails on count.

- [ ] **Step 3 (user): extend `seed_db.py`** — reference implementation:

Add at top of file (after existing imports):

```python
from apps.cinema.models import Genre

GENRE_NAMES = (
    "Action",
    "Comedy",
    "Drama",
    "Horror",
    "Sci-Fi",
    "Animation",
    "Thriller",
    "Romance",
    "Documentary",
)
```

Add a method on `Command` (anywhere after `handle`):

```python
def _seed_genres(self):
    created = 0
    for name in GENRE_NAMES:
        _, was_created = Genre.objects.get_or_create(name=name)
        if was_created:
            created += 1
    return created
```

Inside `handle()`, **at the start of the `with transaction.atomic():` block** (before the user loop):

```python
genres_created = self._seed_genres()
```

- [ ] **Step 4 (user): rerun — expect 2 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): seed 9 named genres in seed_db (idempotent)"
```

---

## Task 3: Halls (random 3-5, capacity 50-200)

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

- [ ] **Step 1 (Claude): append tests**

```python
@pytest.mark.django_db
def test_seed_db_creates_3_to_5_halls():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    count = Hall.objects.count()
    assert 3 <= count <= 5


@pytest.mark.django_db
def test_seed_db_hall_capacities_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for hall in Hall.objects.all():
        assert 50 <= hall.capacity <= 200


@pytest.mark.django_db
def test_seed_db_hall_names_are_unique():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    names = list(Hall.objects.values_list("name", flat=True))
    assert len(names) == len(set(names))
```

- [ ] **Step 2 (user): run — expect 3 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v -k "halls or capac"
```

- [ ] **Step 3 (user): extend `seed_db.py`** — reference:

Update import line: `from apps.cinema.models import Genre, Hall`. Add `import random` at top if not already imported.

```python
def _seed_halls(self):
    count = random.randint(3, 5)
    halls = []
    for i in range(1, count + 1):
        hall = Hall.objects.create(
            name=f"Hall {i}",
            capacity=random.randint(50, 200),
        )
        halls.append(hall)
    return halls
```

In `handle()` after `_seed_genres`:

```python
halls = self._seed_halls()
```

- [ ] **Step 4 (user): rerun — expect 3 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): seed 3-5 random halls in seed_db"
```

---

## Task 4: Actors + Directors

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

**Why combined:** Same model shape, same Faker calls. Two helpers, two commits-worth of work but they're trivially symmetrical — single commit keeps the PR clean.

- [ ] **Step 1 (Claude): append tests**

```python
@pytest.mark.django_db
def test_seed_db_creates_30_actors():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Actor.objects.count() == 30


@pytest.mark.django_db
def test_seed_db_actors_have_names_and_biographies():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for actor in Actor.objects.all():
        assert actor.full_name.strip() != ""
        assert actor.biography.strip() != ""


@pytest.mark.django_db
def test_seed_db_creates_10_directors():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Director.objects.count() == 10


@pytest.mark.django_db
def test_seed_db_directors_have_names_and_biographies():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for director in Director.objects.all():
        assert director.full_name.strip() != ""
        assert director.biography.strip() != ""
```

- [ ] **Step 2 (user): run — expect 4 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v -k "actor or director"
```

- [ ] **Step 3 (user): extend `seed_db.py`** — reference:

Import: `from apps.cinema.models import Actor, Director, Genre, Hall`

```python
def _seed_actors(self, fake):
    actors = []
    for _ in range(30):
        actor = Actor.objects.create(
            full_name=fake.name(),
            biography=fake.paragraph(),
        )
        actors.append(actor)
    return actors

def _seed_directors(self, fake):
    directors = []
    for _ in range(10):
        director = Director.objects.create(
            full_name=fake.name(),
            biography=fake.paragraph(),
        )
        directors.append(director)
    return directors
```

In `handle()` after halls (note: `fake` is already constructed earlier in handle for user names):

```python
actors = self._seed_actors(fake)
directors = self._seed_directors(fake)
```

- [ ] **Step 4 (user): rerun — expect 4 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): seed 30 actors + 10 directors in seed_db"
```

---

## Task 5: Movies (with M2M)

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

**Why now:** Movies need Genres/Actors/Directors (M2M) — those exist after Task 4. Locks in the M2M assignment pattern.

- [ ] **Step 1 (Claude): append tests**

```python
import datetime


@pytest.mark.django_db
def test_seed_db_default_movie_count():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Movie.objects.count() == 20


@pytest.mark.django_db
def test_seed_db_custom_movie_count():
    call_command("seed_db", "--movies=5", stdout=StringIO(), stderr=StringIO())

    assert Movie.objects.count() == 5


@pytest.mark.django_db
def test_seed_db_movie_attributes_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    today = datetime.date.today()
    two_years_ago = today - datetime.timedelta(days=730)
    for movie in Movie.objects.all():
        assert movie.title.strip() != ""
        assert movie.description.strip() != ""
        assert 80 <= movie.duration_minutes <= 180
        assert two_years_ago <= movie.release_date <= today


@pytest.mark.django_db
def test_seed_db_movie_m2m_counts_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for movie in Movie.objects.all():
        assert 1 <= movie.genres.count() <= 3
        assert 3 <= movie.actors.count() <= 8
        assert 1 <= movie.directors.count() <= 2
```

> Note Task 5 introduces `--movies=N` — the CLI flag is added in Task 8, but the test_seed_db_custom_movie_count case will FAIL until Task 8 wires the arg. To keep tasks self-contained, **either**: (a) defer that one test to Task 8, **or** (b) add the `--movies` argparse line as part of Task 5 since the helper needs it anyway. Going with **(b)** — see Step 3 below.

- [ ] **Step 2 (user): run — expect 4 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v -k "movie"
```

- [ ] **Step 3 (user): extend `seed_db.py`** — reference:

Import update: `from apps.cinema.models import Actor, Director, Genre, Hall, Movie`. Add `from datetime import timedelta` and `from django.utils import timezone` if not present.

In `add_arguments`:

```python
parser.add_argument("--movies", type=int, default=20, help="Number of movies to seed (default 20).")
```

```python
def _seed_movies(self, fake, n, genres, actors, directors):
    movies = []
    today = timezone.now().date()
    for _ in range(n):
        movie = Movie.objects.create(
            title=fake.catch_phrase(),
            description=fake.paragraph(nb_sentences=5),
            release_date=today - timedelta(days=random.randint(0, 730)),
            duration_minutes=random.randint(80, 180),
        )
        movie.genres.set(random.sample(genres, k=random.randint(1, 3)))
        movie.actors.set(random.sample(actors, k=random.randint(3, 8)))
        movie.directors.set(random.sample(directors, k=random.randint(1, 2)))
        movies.append(movie)
    return movies
```

In `handle()` after directors:

```python
# Convert genres queryset to list for random.sample (needs sliceable sequence).
genre_list = list(Genre.objects.all())
movies = self._seed_movies(fake, options["movies"], genre_list, actors, directors)
```

- [ ] **Step 4 (user): rerun — expect 4 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): seed N movies with M2M genres/actors/directors"
```

---

## Task 6: Screenings (FK + date arithmetic)

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

- [ ] **Step 1 (Claude): append tests**

```python
from decimal import Decimal


@pytest.mark.django_db
def test_seed_db_default_screening_count():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Screening.objects.count() == 100


@pytest.mark.django_db
def test_seed_db_custom_screening_count():
    call_command("seed_db", "--screenings=15", stdout=StringIO(), stderr=StringIO())

    assert Screening.objects.count() == 15


@pytest.mark.django_db
def test_seed_db_screening_attributes_in_range():
    call_command("seed_db", "--screenings=20", stdout=StringIO(), stderr=StringIO())

    now = timezone.now()
    window_start = now - datetime.timedelta(days=8)  # 1 day buffer
    window_end = now + datetime.timedelta(days=31)
    for screening in Screening.objects.all():
        assert window_start <= screening.start_time <= window_end
        assert Decimal("25.00") <= screening.price <= Decimal("55.00")


@pytest.mark.django_db
def test_seed_db_screenings_use_seeded_movies_and_halls():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    movie_ids = set(Movie.objects.values_list("id", flat=True))
    hall_ids = set(Hall.objects.values_list("id", flat=True))
    for screening in Screening.objects.all():
        assert screening.movie_id in movie_ids
        assert screening.hall_id in hall_ids
```

Add `from django.utils import timezone` at the top of the test file if not already imported.

- [ ] **Step 2 (user): run — expect 4 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v -k "screening"
```

- [ ] **Step 3 (user): extend `seed_db.py`** — reference:

Import update: `from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening`. Add `from decimal import Decimal`.

In `add_arguments`:

```python
parser.add_argument("--screenings", type=int, default=100, help="Number of screenings to seed (default 100).")
```

```python
def _seed_screenings(self, n, movies, halls):
    now = timezone.now()
    for _ in range(n):
        Screening.objects.create(
            movie=random.choice(movies),
            hall=random.choice(halls),
            start_time=now + timedelta(
                days=random.randint(-7, 30),
                hours=random.randint(0, 23),
            ),
            price=Decimal(f"{random.uniform(25, 55):.2f}"),
        )
```

In `handle()` after movies:

```python
self._seed_screenings(options["screenings"], movies, halls)
```

- [ ] **Step 4 (user): rerun — expect 4 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): seed N screenings with random movie+hall+time+price"
```

---

## Task 7: --flush order + non-empty guard for cinema

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`

**Why now:** All cinema entities exist by Task 6, so flush/guard tests can exercise the full surface. The existing tests `test_seed_db_blocks_on_non_empty_db_without_flags` and `test_seed_db_flush_preserves_superuser_wipes_others` still pass (they don't pre-create cinema rows), but we add new tests for cinema-only non-empty + flush ordering.

- [ ] **Step 1 (Claude): append tests**

```python
@pytest.mark.django_db
def test_seed_db_blocks_when_only_cinema_data_exists():
    # No users; just one genre — guard should still trigger.
    Genre.objects.create(name="Action")

    with pytest.raises(CommandError, match="Database not empty"):
        call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 1  # untouched


@pytest.mark.django_db
def test_seed_db_flush_wipes_cinema_data():
    # Pre-create one of each cinema entity.
    g = Genre.objects.create(name="Action")
    h = Hall.objects.create(name="Old Hall", capacity=80)
    Actor.objects.create(full_name="Old Actor")
    Director.objects.create(full_name="Old Director")
    m = Movie.objects.create(
        title="Old Movie",
        description="x",
        release_date=datetime.date(2020, 1, 1),
        duration_minutes=90,
    )
    m.genres.add(g)
    Screening.objects.create(
        movie=m,
        hall=h,
        start_time=timezone.now() + datetime.timedelta(days=1),
        price=Decimal("30.00"),
    )

    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    # Old rows are gone; fresh seed data is in place.
    # "Action" was pre-created AND is in the fixed seed list — after flush there's exactly 1 (the new one).
    assert Genre.objects.count() == 9
    assert Genre.objects.filter(name="Action").count() == 1
    assert not Hall.objects.filter(name="Old Hall").exists()
    assert not Actor.objects.filter(full_name="Old Actor").exists()
    assert not Director.objects.filter(full_name="Old Director").exists()
    assert not Movie.objects.filter(title="Old Movie").exists()
    # Screenings are all fresh.
    assert Screening.objects.count() == 100


@pytest.mark.django_db
def test_seed_db_flush_respects_screening_hall_protect():
    # Reproduce the FK constraint: PROTECT means Screening must die before Hall.
    # If --flush order were wrong this would raise IntegrityError or ProtectedError.
    h = Hall.objects.create(name="Protected Hall", capacity=100)
    m = Movie.objects.create(
        title="x", description="x",
        release_date=datetime.date(2024, 1, 1), duration_minutes=100,
    )
    Screening.objects.create(
        movie=m, hall=h,
        start_time=timezone.now() + datetime.timedelta(days=1),
        price=Decimal("30.00"),
    )

    # Must NOT raise.
    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    assert not Hall.objects.filter(name="Protected Hall").exists()
```

- [ ] **Step 2 (user): run — expect 3 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v -k "blocks_when_only_cinema or flush_wipes_cinema or hall_protect"
```

Expected failures: the non-empty guard ignores cinema entities, and `--flush` only wipes users — Hall + Screening + Movie are still there, causing assertion failures.

- [ ] **Step 3 (user): extend `seed_db.py`** — reference:

Widen the guard. Replace the existing block:

```python
non_super_count = User.objects.filter(is_superuser=False).count()

if options["flush"] or options["append"]:
    pass
elif non_super_count > 0:
    raise CommandError(
        f"Database not empty (found {non_super_count} non-superuser user(s)). "
        f"Use --flush to wipe non-superusers or --append to add only missing."
    )
```

With:

```python
non_super_count = User.objects.filter(is_superuser=False).count()
cinema_count = (
    Genre.objects.count()
    + Hall.objects.count()
    + Actor.objects.count()
    + Director.objects.count()
    + Movie.objects.count()
    + Screening.objects.count()
)

if options["flush"] or options["append"]:
    pass
elif non_super_count > 0 or cinema_count > 0:
    raise CommandError(
        f"Database not empty (found {non_super_count} non-superuser user(s), "
        f"{cinema_count} cinema row(s)). Use --flush to wipe or --append to add."
    )
```

Inside `if options["flush"]:` block (currently just `User.objects.filter(is_superuser=False).delete()`), prepend cinema flushing in FK-safe order:

```python
if options["flush"]:
    # FK-safe order — Screening.hall is PROTECT.
    Screening.objects.all().delete()
    Movie.objects.all().delete()
    Hall.objects.all().delete()
    Actor.objects.all().delete()
    Director.objects.all().delete()
    Genre.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()
```

- [ ] **Step 4 (user): rerun — expect 3 PASS**

- [ ] **Step 5 (user): run the full suite to make sure nothing regressed**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

All ~24 tests should pass.

- [ ] **Step 6 (user): commit**

```bash
git add tests/cinema/test_seed_db.py apps/cinema/management/commands/seed_db.py
git commit -m "feat(FR-13): extend non-empty guard + --flush for cinema entities"
```

---

## Task 8: Summary output + coverage + smoke + PR

**Files:**
- Modify: `tests/cinema/test_seed_db.py`
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (Claude): append test for the success summary line**

```python
@pytest.mark.django_db
def test_seed_db_success_output_mentions_cinema_counts():
    stdout = StringIO()
    call_command("seed_db", stdout=stdout, stderr=StringIO())

    out = stdout.getvalue()
    assert "9 genres" in out
    assert "movies" in out
    assert "screenings" in out
    assert "users" in out
```

- [ ] **Step 2 (user): run — expect 1 FAIL**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_success_output_mentions_cinema_counts -v
```

- [ ] **Step 3 (user): update the success message in `seed_db.py`** — reference. Replace the existing `self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} users ..."))` line (in the non-append branch) with a multi-entity summary:

```python
self.stdout.write(
    self.style.SUCCESS(
        f"Seeded {Genre.objects.count()} genres, "
        f"{Hall.objects.count()} halls, "
        f"{Actor.objects.count()} actors, "
        f"{Director.objects.count()} directors, "
        f"{Movie.objects.count()} movies, "
        f"{Screening.objects.count()} screenings, "
        f"and {created_count} users ({active_count} active, "
        f"{inactive_count} inactive). Default password: {password}."
    )
)
```

(Update the `--append` success line similarly if you want — out of scope for the required test, but nicer UX.)

- [ ] **Step 4 (user): rerun all tests + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: all tests pass; `apps/cinema/management/commands/seed_db.py` ≥ 90% (some branches like `--force` warning path may stay uncovered without dedicated tests).

- [ ] **Step 5 (user): manual smoke**

```bash
# Wipe + reseed
poetry run python manage.py seed_db --flush
# Visit admin
poetry run python manage.py runserver
```

Open `/admin/cinema/movie/` — confirm ~20 movies render with M2M relations populated. Open `/admin/cinema/screening/` is gone (deferred to US-28); instead open a movie detail and confirm `screenings_count` shows realistic values.

- [ ] **Step 6 (Claude): update `.Claude/backlog.md` §7** — US-16 → Done; queue **US-11** (MovieList view, FR-01) next per `.Claude/m2_planning.md` ordering.

- [ ] **Step 7 (user): commit backlog update**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-16 done, queue US-11 next"
```

- [ ] **Step 8 (user): push + open PR**

```bash
git push -u origin feat/FR-13-seed-db-movies
```

PR body:

```
Title: feat(FR-13): seed cinema entities (Genres/Halls/Actors/Directors/Movies/Screenings) — US-16

## Summary
- Extend `seed_db` to also create Genre/Hall/Actor/Director/Movie/Screening data
- New flags: `--movies=N` (default 20), `--screenings=N` (default 100)
- Fixed: 9 named genres (idempotent on --append), 3-5 random halls, 30 actors, 10 directors
- Movies: catch_phrase title, 80-180 min duration, release_date last 2 years, M2M to 1-3 genres / 3-8 actors / 1-2 directors
- Screenings: random movie+hall, start_time -7 to +30 days, price 25.00-55.00
- Non-empty guard widened to count cinema rows
- `--flush` deletes in FK-safe order (Screening PROTECTs Hall → screenings first)
- ~20 new tests

## Closes
- US-16 (FR-13 M2 scope)

## Spec & Plan
- Plan: `docs/superpowers/plans/2026-05-20-seed-db-movies.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-13 M2

## Out of scope (deferred)
- Bookings + StripeEvent seeding → US-18+ (M3, FR-13 §M3)
- Photo/poster uploads → blank (admin renders "—")

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: `seed_db --flush` produces browsable catalog in admin
- [ ] M2M relations populated on Movie rows
- [ ] Default counts: 9 genres, 3-5 halls, 30 actors, 10 directors, 20 movies, 100 screenings, 10 users
```

- [ ] **Step 9 (after merge — separate session): update `memory/project_kinomania_bootstrap.md`** — M2 progress: 3/8 done.

---

## Self-review summary

- ✅ All FR-13 M2 entities seeded (Genre/Hall/Actor/Director/Movie/Screening).
- ✅ All required flags (`--movies`, `--screenings`) wired with documented defaults.
- ✅ FK-safe flush order (Screening PROTECT pitfall) explicitly tested.
- ✅ Idempotent genres on `--append` matches spec ("create only missing" spirit).
- ✅ M2M range assertions (1-3 / 3-8 / 1-2) match FR-13 spec.
- ✅ Out-of-scope (bookings, photos) explicitly deferred to US-18+.
- ✅ Existing US-08 tests untouched (still 10 users; user side unchanged).
- ✅ No placeholders; every step has runnable code/commands.
- ✅ One commit per entity → small reviewable diffs.
