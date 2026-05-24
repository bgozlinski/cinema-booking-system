# US-28 — Admin: BookingAdmin + ScreeningAdmin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the booking-side admin (FR-11, last M3 story): upgrade `BookingAdmin` (total price, filters, list-editable status) and add `ScreeningAdmin` with colored availability badges — both N+1-free via `get_queryset`.

**Architecture:** Mirror the US-15/US-17 admin pattern (`get_queryset` with `select_related`/`annotate`, `@admin.display`). `ScreeningAdmin` inlines the booked-count annotation so `available_seats_count()`/`booked_seats_count()` (which short-circuit on `_annotated_booked_count`) don't N+1; the badge colors availability <20% red / 20-50% yellow / >50% green. Budget tests guard both changelists.

**Tech Stack:** Django admin (`ModelAdmin`, `TabularInline`, `@admin.display`, `format_html`), `annotate(Coalesce(Sum(filter=Q(...))))`, pytest-django `django_assert_max_num_queries`.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-24-us28-booking-admin.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (budget tests + shape/badge updates).
- Kod aplikacji (`apps/booking/admin.py`, `apps/cinema/admin.py`) — **default: user wkleja** z planu.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

Branch `feat/FR-11-booking-admin` (już utworzony). Spec + plan jako pierwszy commit:

```bash
git add docs/superpowers/specs/2026-05-24-us28-booking-admin.md \
        docs/superpowers/plans/2026-05-24-us28-booking-admin.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-28 booking/screening admin design and plan

Planning for US-28 (FR-11, last M3) — full BookingAdmin (total price, filters,
list-editable status) + ScreeningAdmin with colored availability badges. N+1-free
via get_queryset select_related + booked-count annotate (US-15/US-17 pattern).
No migrations.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/admin.py` | Modify | BookingAdmin upgrade |
| `apps/cinema/admin.py` | Modify | + ScreeningAdmin + BookingInline |
| `tests/cinema/test_admin_query_budgets.py` | Modify | + 2 budget classes |
| `tests/booking/test_admin.py` | Modify | BookingAdmin shape |
| `tests/cinema/test_admin.py` | Modify | + ScreeningAdmin registration + badge |
| `.Claude/backlog.md` | Modify | US-28 → Done (po merge) |

No migrations.

---

## Task 1: BookingAdmin upgrade

**Files:**
- Test: `tests/booking/test_admin.py` (Modify), `tests/cinema/test_admin_query_budgets.py` (Modify — add `TestBookingAdminQueryBudget`)
- Modify: `apps/booking/admin.py`

- [ ] **Step 1: Update/add tests** (Claude writes) — BookingAdmin shape in `tests/booking/test_admin.py` (assert `total_price_display` in `list_display`, `list_editable == ("status",)`, helper returns `total_price`) and add `TestBookingAdminQueryBudget` to `tests/cinema/test_admin_query_budgets.py` (12 bookings, `admin:booking_booking_changelist`, cap 12).

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_admin.py tests/cinema/test_admin_query_budgets.py::TestBookingAdminQueryBudget -v`
Expected: FAIL — `total_price_display` not in list_display / budget exceeded (no select_related yet).

- [ ] **Step 3: Replace `apps/booking/admin.py`** (user pastes)

```python
from django.contrib import admin

from apps.booking.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "screening",
        "seats_count",
        "status",
        "total_price_display",
        "created_at",
    )
    list_filter = ("status", "screening__movie", "created_at")
    list_editable = ("status",)
    search_fields = ("user__email", "screening__movie__title")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "screening__movie")

    @admin.display(description="total price")
    def total_price_display(self, obj):
        return obj.total_price
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_admin.py tests/cinema/test_admin_query_budgets.py::TestBookingAdminQueryBudget -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/booking/admin.py tests/booking/test_admin.py tests/cinema/test_admin_query_budgets.py
git commit -m "$(cat <<'EOF'
feat(FR-11): full BookingAdmin (total price, filters, list-editable status)

Upgrade the minimal US-18 BookingAdmin: total_price_display column, list_filter on
status/movie/created_at, list_editable status, and select_related("user",
"screening__movie") in get_queryset to kill the __str__/total_price N+1. Budget
test caps the changelist.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: ScreeningAdmin + availability badges

**Files:**
- Test: `tests/cinema/test_admin.py` (Modify), `tests/cinema/test_admin_query_budgets.py` (Modify — add `TestScreeningAdminQueryBudget`)
- Modify: `apps/cinema/admin.py`

- [ ] **Step 1: Add tests** (Claude writes) — ScreeningAdmin registration + `available_seats_display` color (via `ma.get_queryset(RequestFactory().get("/admin/")).get(pk=...)` adapter so the annotation is present) in `tests/cinema/test_admin.py`; add `TestScreeningAdminQueryBudget` (12 screenings × 2 PENDING bookings, `admin:cinema_screening_changelist`, cap 12) to `tests/cinema/test_admin_query_budgets.py`.

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py::TestScreeningAdminQueryBudget -v`
Expected: FAIL — `Screening` not registered (`NoReverseMatch admin:cinema_screening_changelist`).

- [ ] **Step 3: Add to `apps/cinema/admin.py`** (user pastes)

Update imports (top of file):

```python
from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
```

Append at the end of the file:

```python
class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("user", "seats_count", "status", "created_at")
    readonly_fields = ("user", "seats_count", "status", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "start_time",
        "hall",
        "price",
        "available_seats_display",
        "booked_seats_display",
    )
    list_filter = ("hall", "movie", "start_time")
    search_fields = ("movie__title",)
    date_hierarchy = "start_time"
    inlines = (BookingInline,)

    def get_queryset(self, request):
        now = timezone.now()
        return (
            super()
            .get_queryset(request)
            .select_related("movie", "hall")
            .annotate(
                _annotated_booked_count=Coalesce(
                    Sum(
                        "bookings__seats_count",
                        filter=(
                            Q(bookings__status=BookingStatus.CONFIRMED)
                            | Q(
                                bookings__status=BookingStatus.PENDING,
                                bookings__expires_at__gt=now,
                            )
                        ),
                    ),
                    0,
                )
            )
        )

    @admin.display(description="booked")
    def booked_seats_display(self, obj):
        return obj.booked_seats_count()

    @admin.display(description="available")
    def available_seats_display(self, obj):
        available = obj.available_seats_count()
        capacity = obj.hall.capacity
        ratio = available / capacity if capacity else 0
        if ratio > 0.5:
            color = "green"
        elif ratio >= 0.2:
            color = "orange"
        else:
            color = "red"
        return format_html('<b style="color: {};">{}</b>', color, available)
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py::TestScreeningAdminQueryBudget -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py
git commit -m "$(cat <<'EOF'
feat(FR-11): add ScreeningAdmin with colored availability badges

ScreeningAdmin shows available/booked seats with a colored badge (>50% green,
20-50% orange, <20% red) + a read-only BookingInline. get_queryset select_relates
movie/hall and annotates the booked-seat count (CONFIRMED | active-PENDING) so the
badge helpers stay N+1-free. Budget test caps the changelist.

Closes US-28.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking apps/cinema tests
poetry run ruff format --check apps/booking apps/cinema tests
poetry run mypy apps/booking apps/cinema
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0; full suite green; coverage ≥80%.

> If a budget test's cap is too tight (list_editable formset / list_filter dropdown queries), measure the actual count and bump the cap (the existing US-17 tests carry the same "tighten after measurement" note). If too loose to be meaningful, lower it.

- [ ] **Step 2: Manual smoke**

```bash
# /admin/cinema/screening/ → colored availability badges; open a screening → BookingInline
# /admin/booking/booking/ → total price column, status editable inline, filters
```

---

## Task 4: Backlog + PR + M3 close

- [ ] **Step 1: Update `.Claude/backlog.md`**

- `Done` → add US-28; **M3 COMPLETE (11/11)**
- `Ready (DoR ✅)` → US-29 (M4 — DRF setup) — brainstorm-required (new milestone)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-28 done — M3 COMPLETE (booking web + Stripe)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-11-booking-admin
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-28) / DoD / Test plan / Out of scope (ScreeningInline on Movie/Hall).

- [ ] **Step 3: After merge — cut `v0.3.0`** (M3 complete)

```bash
git checkout main && git pull
git tag -a v0.3.0 -m "v0.3.0 — Booking web + Stripe (M3 complete)"
git push origin v0.3.0
gh release create v0.3.0 --title "v0.3.0 — Booking web + Stripe" --notes "M3: booking flow + Stripe Checkout/webhook/refund + expire + admin"
```

---

## Self-Review (wykonane)

**Spec coverage:** §3 BookingAdmin → Task 1. §4 ScreeningAdmin/BookingInline → Task 2. §5 tests → Tasks 1-2 (budget ×2 + shape + badge + registration). §6 DoD → covered incl. M3 close (Task 4). §7 risk #1 (cap) → Task 3 note; #2 (badge annotation adapter) → Task 2 Step 1.

**Placeholder scan:** Task 1 Step 1 + Task 2 Step 1 describe the test edits prose-style (exact content written by Claude at execution, since they modify existing files with read-then-edit) — not placeholders; the budget-test bodies + admin code blocks are complete. No TBD/TODO.

**Type consistency:** `total_price_display`/`available_seats_display`/`booked_seats_display` `@admin.display` helpers consistent (admin + tests). `_annotated_booked_count` matches `Screening.booked_seats_count`'s short-circuit attr (US-18). Admin URL names `admin:booking_booking_changelist` / `admin:cinema_screening_changelist` consistent (budget tests). Badge colors green/orange/red consistent (admin + badge test).
