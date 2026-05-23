# US-24 — Stripe Checkout integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the US-20 `create_checkout_session` stub with real Stripe Checkout (FR-21): book → redirect to Stripe hosted page → pay → back to `/bookings/<id>/?stripe=success`, plus a retry endpoint for failed/expired checkouts.

**Architecture:** Three layers — `payments.services.create_checkout_session` (real `stripe.checkout.Session.create`, raises `StripeError`), `booking.services.start_checkout` (persists `stripe_session_id`, returns url, reused by create + retry), and `create_booking` refactored to return `Booking` (PENDING only; Stripe extracted). Views: `BookingCreateView` orchestrates create→checkout (failure → detail+flash), new `BookingCheckoutView` retry, `BookingDetailView` handles `?stripe=`. Stripe SDK mocked in tests via a shared `mock_checkout_session` fixture.

**Tech Stack:** `stripe` SDK, Django 6 CBV, `environ.Env` config, pytest-django + `pytest-mock`, `@pytest.mark.stripe`.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-24-us24-stripe-checkout-design.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (conftest fixture + payments/booking test files).
- Kod aplikacji (`apps/payments/services.py`, `apps/booking/services.py`, `views.py`, `urls.py`, `templates/booking/booking_detail.html`, `settings/base.py`, `.env.example`, `poetry add stripe`) — **default: user wkleja/uruchamia** z planu.
- User odpala wszystkie komendy `git`/`gh` + `poetry`/`pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-21-stripe-checkout
git branch --show-current   # → feat/FR-21-stripe-checkout
```

Spec + plan jako pierwszy commit:

```bash
git add docs/superpowers/specs/2026-05-24-us24-stripe-checkout-design.md \
        docs/superpowers/plans/2026-05-24-us24-stripe-checkout.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-24 Stripe Checkout design and plan

Brainstorming + planning for US-24 (FR-21). Replace the create_checkout_session
stub with real stripe.checkout.Session.create; extract start_checkout + refactor
create_booking to return Booking; add retry endpoint POST /bookings/<id>/checkout/;
?stripe= flash on detail. Per-call uuid idempotency key; omit session expires_at;
shared mock_checkout_session fixture. Webhook/refund/admin deferred to US-25/27/28.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `settings/base.py` | Modify | `STRIPE_API_KEY`, `BASE_URL` |
| `.env.example` | Modify | Stripe key + BASE_URL block |
| `pyproject.toml` / `poetry.lock` | Modify | `poetry add stripe` |
| `apps/payments/services.py` | Modify | real `create_checkout_session` |
| `apps/booking/services.py` | Modify | + `start_checkout`; refactor `create_booking` → `Booking` |
| `apps/booking/views.py` | Modify | refactor `BookingCreateView`; + `BookingCheckoutView`; extend `BookingDetailView` |
| `apps/booking/urls.py` | Modify | + `booking:checkout` |
| `templates/booking/booking_detail.html` | Modify | "Zapłać" button (PENDING) |
| `tests/conftest.py` | Create/Modify | `mock_checkout_session` fixture |
| `tests/payments/test_services.py` | Modify | rewrite real-mocked |
| `tests/booking/test_services.py` | Modify | create_booking → Booking; + `TestStartCheckout` |
| `tests/booking/test_views.py` | Modify | create-view Stripe redirect / failure |
| `tests/booking/test_checkout_view.py` | Create | retry endpoint |
| `tests/booking/test_detail_view.py` | Modify | `?stripe=` + pay button |
| `.Claude/backlog.md` | Modify | US-24 → Done (po merge) |

No migrations.

---

## Task 1: Config — install Stripe + settings

**Files:** `pyproject.toml`, `settings/base.py`, `.env.example`

- [ ] **Step 1: Install the SDK** (user runs)

```bash
poetry add stripe
```

- [ ] **Step 2: Add settings** (user edits `settings/base.py`, near other `env(...)` reads)

```python
STRIPE_API_KEY = env("STRIPE_API_KEY", default="")
BASE_URL = env("BASE_URL", default="http://localhost:8000")
```

- [ ] **Step 3: Extend `.env.example`** (user edits)

```
# Stripe (test mode) — keys at https://dashboard.stripe.com/test/apikeys
STRIPE_API_KEY=sk_test_xxx
BASE_URL=http://localhost:8000
# STRIPE_WEBHOOK_SECRET added in US-25 (via `stripe listen`)
```

- [ ] **Step 4: Sanity** — `poetry run python -c "import stripe; print(stripe.VERSION)"` prints a version.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml poetry.lock settings/base.py .env.example
git commit -m "$(cat <<'EOF'
chore(FR-21): add stripe SDK + STRIPE_API_KEY/BASE_URL settings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Real create_checkout_session + mock fixture

**Files:**
- Create/Modify: `tests/conftest.py`
- Test: `tests/payments/test_services.py` (rewrite)
- Modify: `apps/payments/services.py`

- [ ] **Step 1: Add the `mock_checkout_session` fixture** to `tests/conftest.py` (Claude writes)

```python
import pytest


@pytest.fixture
def mock_checkout_session(mocker):
    """Patch stripe.checkout.Session.create with a fake session.

    Returns the patched mock. Default returns a fake session (.url + .id); set
    `.side_effect = stripe.error.APIConnectionError("boom")` to simulate failure.
    """
    fake = mocker.MagicMock(url="https://checkout.stripe.test/c/cs_test_123", id="cs_test_123")
    return mocker.patch(
        "apps.payments.services.stripe.checkout.Session.create", return_value=fake
    )
```

> If `tests/conftest.py` already exists, append the fixture (and `import pytest` if missing).

- [ ] **Step 2: Rewrite `tests/payments/test_services.py`** (Claude writes)

```python
"""Tests for the real Stripe checkout session creation (US-24 / FR-21)."""

import stripe
from django.conf import settings
from django.urls import reverse

from apps.payments.services import create_checkout_session
from tests.booking.factories import BookingFactory

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def test_creates_session_with_expected_params(mock_checkout_session):
    booking = BookingFactory(seats_count=2)
    create_checkout_session(booking)

    kwargs = mock_checkout_session.call_args.kwargs
    assert kwargs["mode"] == "payment"
    assert kwargs["client_reference_id"] == str(booking.id)
    item = kwargs["line_items"][0]
    assert item["price_data"]["currency"] == "pln"
    assert item["price_data"]["unit_amount"] == int(booking.total_price * 100)
    detail = reverse("booking:detail", kwargs={"pk": booking.id})
    assert kwargs["success_url"] == f"{settings.BASE_URL}{detail}?stripe=success"
    assert kwargs["cancel_url"] == f"{settings.BASE_URL}{detail}?stripe=cancelled"
    assert "idempotency_key" in kwargs


def test_returns_url_and_session_id(mock_checkout_session):
    booking = BookingFactory()
    url, session_id = create_checkout_session(booking)
    assert url == "https://checkout.stripe.test/c/cs_test_123"
    assert session_id == "cs_test_123"


def test_propagates_stripe_error(mock_checkout_session):
    mock_checkout_session.side_effect = stripe.error.APIConnectionError("network down")
    with pytest.raises(stripe.error.StripeError):
        create_checkout_session(BookingFactory())
```

- [ ] **Step 3: Run → RED**

Run: `poetry run pytest tests/payments/test_services.py -v`
Expected: FAIL — old stub returns movie_detail url; `Session.create` not called (mock `call_args` is None).

- [ ] **Step 4: Replace `apps/payments/services.py`** (user pastes)

```python
import uuid

import stripe
from django.conf import settings
from django.urls import reverse

from apps.booking.models import Booking

stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Create a real Stripe Checkout Session for a PENDING booking (FR-21).

    Returns (checkout_url, session_id). Raises stripe.error.StripeError on
    API/network failure — the caller handles it. No DB writes here.
    """
    detail_path = reverse("booking:detail", kwargs={"pk": booking.id})
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "unit_amount": int(booking.total_price * 100),
                    "product_data": {
                        "name": f"Booking #{booking.id} — {booking.screening.movie.title}",
                    },
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(booking.id),
        success_url=f"{settings.BASE_URL}{detail_path}?stripe=success",
        cancel_url=f"{settings.BASE_URL}{detail_path}?stripe=cancelled",
        idempotency_key=uuid.uuid4().hex,
    )
    return session.url, session.id
```

- [ ] **Step 5: Run → GREEN**

Run: `poetry run pytest tests/payments/test_services.py -v`
Expected: PASS (3 tests).

> mypy note: if `session.url` is typed `str | None`, change the return to `return session.url or "", session.id`. Decide at the Task 6 gate.

- [ ] **Step 6: Commit**

```bash
git add apps/payments/services.py tests/payments/test_services.py tests/conftest.py
git commit -m "$(cat <<'EOF'
feat(FR-21): real Stripe Checkout session creation

Replace the create_checkout_session stub with stripe.checkout.Session.create
(mode=payment, PLN line item, client_reference_id, success/cancel URLs via
BASE_URL, per-call uuid idempotency key). Raises StripeError on failure. Add a
shared mock_checkout_session fixture for Stripe-marked tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Refactor create_booking + add start_checkout + create view

**Files:**
- Test: `tests/booking/test_services.py`, `tests/booking/test_views.py` (Modify)
- Modify: `apps/booking/services.py`, `apps/booking/views.py`

- [ ] **Step 1: Update `tests/booking/test_services.py`** (Claude writes)

In `TestCreateBookingSuccess`, change the unpack in `test_creates_pending_with_expiry` and **remove** the two stub-era tests, then add `TestStartCheckout`:

```python
# test_creates_pending_with_expiry: change first line to:
        booking = create_booking(user=user, screening=screening, seats_count=3)
# (drop the `, _url` unpack; the rest of the asserts stay)

# DELETE test_returns_movie_detail_checkout_url
# DELETE test_does_not_set_session_id_with_stub
```

Add at the end of the file (with `start_checkout` added to the services import, and `mock_checkout_session` available):

```python
@pytest.mark.stripe
class TestStartCheckout:
    def test_saves_session_id_and_returns_url(self, mock_checkout_session):
        booking = BookingFactory()
        url = start_checkout(booking=booking)
        assert url == "https://checkout.stripe.test/c/cs_test_123"
        booking.refresh_from_db()
        assert booking.stripe_session_id == "cs_test_123"

    def test_propagates_stripe_error(self, mock_checkout_session):
        import stripe

        mock_checkout_session.side_effect = stripe.error.APIConnectionError("boom")
        with pytest.raises(stripe.error.StripeError):
            start_checkout(booking=BookingFactory())
```

Update the services import at the top:

```python
from apps.booking.services import (
    BookingNotCancellableError,
    NotEnoughSeatsError,
    ScreeningInPastError,
    cancel_booking,
    create_booking,
    start_checkout,
)
```

- [ ] **Step 2: Update `tests/booking/test_views.py`** (Claude writes)

Replace `test_valid_creates_booking_and_redirects`, **remove** `test_valid_sets_success_message`, add `test_stripe_failure_redirects_to_detail`. Add `from apps.booking.models import Booking, BookingStatus` (already present) and the `stripe` import where needed.

```python
    def test_valid_creates_booking_and_redirects_to_stripe(self, client, mock_checkout_session):
        user = UserFactory()
        client.force_login(user)
        screening = _future_screening(capacity=50)
        resp = client.post(_book_url(screening), {"seats_count": 3})
        assert resp.status_code == 302
        assert resp.url == "https://checkout.stripe.test/c/cs_test_123"
        booking = Booking.objects.get(user=user, screening=screening)
        assert booking.status == BookingStatus.PENDING
        assert booking.stripe_session_id == "cs_test_123"

    def test_stripe_failure_redirects_to_detail(self, client, mock_checkout_session):
        import stripe

        mock_checkout_session.side_effect = stripe.error.APIConnectionError("boom")
        user = UserFactory()
        client.force_login(user)
        screening = _future_screening(capacity=50)
        resp = client.post(_book_url(screening), {"seats_count": 3})
        booking = Booking.objects.get(user=user, screening=screening)
        assert resp.status_code == 302
        assert resp.url == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert booking.status == BookingStatus.PENDING  # left for retry
```

Mark the two Stripe-touching tests with `@pytest.mark.stripe` (add the decorator above each, or add `pytest.mark.stripe` to a class). Keep `test_invalid_form_rerenders_no_booking`, `test_service_error_rerenders_with_nonfield_error`, `test_past_screening_rerenders_with_error`, and the `TestAuth`/`TestGet` tests unchanged.

- [ ] **Step 3: Run → RED**

Run: `poetry run pytest tests/booking/test_services.py tests/booking/test_views.py -v`
Expected: FAIL — `ImportError: cannot import name 'start_checkout'` / `create_booking` still returns a tuple / view still redirects to movie_detail.

- [ ] **Step 4: Refactor `apps/booking/services.py`** (user pastes)

Change `create_booking` to return `Booking` (drop the trailing Stripe block + tuple return — see spec §4), and add `start_checkout`:

```python
def create_booking(*, user, screening: Screening, seats_count: int) -> Booking:
    """Create a PENDING booking race-safely (FR-07). Returns the booking.

    The Stripe checkout session is created separately by start_checkout (US-24).
    Caller owns seats_count range [1, 10].
    """
    with transaction.atomic():
        locked = Screening.objects.select_for_update().get(pk=screening.pk)
        if locked.is_in_past():
            raise ScreeningInPastError()
        available = locked.available_seats_count()
        if seats_count > available:
            raise NotEnoughSeatsError(available=available)
        booking = Booking.objects.create(
            user=user,
            screening=locked,
            seats_count=seats_count,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
    return booking


def start_checkout(*, booking: Booking) -> str:
    """Create a Stripe Checkout session for a PENDING booking; return its URL.

    Persists the returned stripe_session_id. Lets stripe.error.StripeError
    propagate to the view. Shared by create + retry flows.
    """
    checkout_url, session_id = create_checkout_session(booking)
    booking.stripe_session_id = session_id
    booking.save(update_fields=["stripe_session_id"])
    return checkout_url
```

Keep the `from apps.payments.services import create_checkout_session` import (now used by `start_checkout`).

- [ ] **Step 5: Refactor `BookingCreateView.post` in `apps/booking/views.py`** (user pastes)

Add imports: `import stripe`, and `start_checkout` to the services import. Replace `post`:

```python
    def post(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(request.POST, screening=screening)
        if not form.is_valid():
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            booking = create_booking(
                user=request.user,
                screening=screening,
                seats_count=form.cleaned_data["seats_count"],
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.error.StripeError:
            messages.error(
                request,
                "Płatność jest chwilowo niedostępna — spróbuj ponownie z poziomu rezerwacji.",
            )
            return redirect("booking:detail", pk=booking.pk)
        return redirect(checkout_url)
```

(Services import becomes `from apps.booking.services import BookingError, cancel_booking, create_booking, start_checkout`.)

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_services.py tests/booking/test_views.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/booking/services.py apps/booking/views.py \
        tests/booking/test_services.py tests/booking/test_views.py
git commit -m "$(cat <<'EOF'
refactor(FR-21): split checkout out of create_booking; wire create view to Stripe

create_booking now returns the PENDING Booking only; start_checkout creates the
Stripe session and persists stripe_session_id (shared by create + retry flows).
BookingCreateView redirects to the Stripe hosted page on success, or to the
booking detail with an error flash if the Stripe call fails (booking left PENDING
for retry).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Retry endpoint + pay button

**Files:**
- Test: `tests/booking/test_checkout_view.py` (Create)
- Modify: `apps/booking/views.py`, `apps/booking/urls.py`, `templates/booking/booking_detail.html`

- [ ] **Step 1: Write `tests/booking/test_checkout_view.py`** (Claude writes)

```python
"""Tests for BookingCheckoutView retry endpoint (US-24 / FR-21)."""

import pytest
import stripe
from django.urls import reverse

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def _checkout_url(booking):
    return reverse("booking:checkout", kwargs={"pk": booking.pk})


class TestBookingCheckoutView:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url

    def test_get_not_allowed(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_checkout_url(booking))
        assert resp.status_code == 405

    def test_owner_pending_redirects_to_stripe(self, client, mock_checkout_session):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 302
        assert resp.url == "https://checkout.stripe.test/c/cs_test_123"
        booking.refresh_from_db()
        assert booking.stripe_session_id == "cs_test_123"

    def test_non_pending_flashes_error(self, client, mock_checkout_session):
        booking = ConfirmedBookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert any("nie można" in str(m).lower() for m in resp.context["messages"])
        assert mock_checkout_session.call_count == 0

    def test_stripe_failure_flashes_error(self, client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.error.APIConnectionError("boom")
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert any("niedostępna" in str(m).lower() for m in resp.context["messages"])

    def test_non_owner_404(self, client, mock_checkout_session):
        booking = BookingFactory()
        client.force_login(UserFactory())
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 404
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_checkout_view.py -v`
Expected: FAIL — `NoReverseMatch` for `booking:checkout`.

- [ ] **Step 3: Add `BookingCheckoutView` to `apps/booking/views.py`** (user pastes)

```python
class BookingCheckoutView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        if booking.status != BookingStatus.PENDING:
            messages.error(request, "Tej rezerwacji nie można już opłacić.")
            return redirect("booking:detail", pk=booking.pk)
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.error.StripeError:
            messages.error(request, "Płatność jest chwilowo niedostępna — spróbuj ponownie.")
            return redirect("booking:detail", pk=booking.pk)
        return redirect(checkout_url)
```

Ensure `BookingStatus` is imported: `from apps.booking.models import Booking, BookingStatus`.

> mypy: `get_object_or_404(Booking, pk=pk, user=request.user)` — same `[misc]` user-lookup as dev pitfall #12. Use `user=cast("User", request.user)` (TYPE_CHECKING import from US-22) if flagged.

- [ ] **Step 4: Add route to `apps/booking/urls.py`** (user edits)

```python
    path("bookings/<int:pk>/checkout/", BookingCheckoutView.as_view(), name="checkout"),
```

(import `BookingCheckoutView`; place near `cancel`/`detail`.)

- [ ] **Step 5: Add the "Zapłać" button to `templates/booking/booking_detail.html`** (user edits)

Inside `{% block content %}`, after the card (single line — Django tag rules):

```django
  {% if booking.status == 'PENDING' %}<form method="post" action="{% url 'booking:checkout' pk=booking.pk %}" class="mt-3">{% csrf_token %}<button type="submit" class="btn btn-success">Zapłać</button></form>{% endif %}
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_checkout_view.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/booking/views.py apps/booking/urls.py \
        templates/booking/booking_detail.html tests/booking/test_checkout_view.py
git commit -m "$(cat <<'EOF'
feat(FR-21): add checkout retry endpoint + pay button

POST /bookings/<id>/checkout/ (booking:checkout) re-creates a Stripe session for a
PENDING booking owned by the user (flash + redirect if not PENDING or Stripe
fails). The booking detail page shows a "Zapłać" button for PENDING bookings.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Detail `?stripe=` handling

**Files:**
- Test: `tests/booking/test_detail_view.py` (Modify)
- Modify: `apps/booking/views.py`

- [ ] **Step 1: Append tests to `tests/booking/test_detail_view.py`** (Claude writes)

```python
class TestBookingDetailStripeReturn:
    def test_stripe_success_shows_info_message(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking) + "?stripe=success")
        assert any("potwierdzenie" in str(m).lower() for m in resp.context["messages"])

    def test_stripe_cancelled_shows_warning(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking) + "?stripe=cancelled")
        assert any("anulowana" in str(m).lower() for m in resp.context["messages"])

    def test_pay_button_shown_for_pending(self, client):
        booking = BookingFactory()  # PENDING
        client.force_login(booking.user)
        content = client.get(_detail_url(booking)).content.decode()
        assert reverse("booking:checkout", kwargs={"pk": booking.pk}) in content
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_detail_view.py::TestBookingDetailStripeReturn -v`
Expected: FAIL — no messages added / `booking:checkout` not in content (until Task 4 template lands; if Task 4 done, only the message tests fail).

- [ ] **Step 3: Add `get` override to `BookingDetailView`** (user pastes)

```python
    def get(self, request, *args, **kwargs):
        stripe_status = request.GET.get("stripe")
        if stripe_status == "success":
            messages.info(request, "Płatność przyjęta — potwierdzenie rezerwacji wkrótce.")
        elif stripe_status == "cancelled":
            messages.warning(request, "Płatność anulowana. Możesz spróbować ponownie.")
        return super().get(request, *args, **kwargs)
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_detail_view.py -v`
Expected: PASS (existing 8 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add apps/booking/views.py tests/booking/test_detail_view.py
git commit -m "$(cat <<'EOF'
feat(FR-21): flash payment result on booking detail (?stripe=)

BookingDetailView shows an info flash on ?stripe=success ("confirmation coming" —
status stays PENDING until the US-25 webhook) and a warning on ?stripe=cancelled.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking apps/payments tests
poetry run ruff format --check apps/booking apps/payments tests
poetry run mypy apps/booking apps/payments
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0; full suite green; coverage ≥80%.

> Likely mypy fixes (decide per output): `session.url` typed `str | None` → `return session.url or "", session.id`; checkout view `user=...` lookup → `cast("User", request.user)`.

- [ ] **Step 2: Manual smoke (Stripe test mode — optional, needs real `sk_test_` in `.env`)**

```bash
# terminal: poetry run python manage.py runserver
# browser: login → book a screening → redirected to Stripe Checkout
# pay with 4242 4242 4242 4242 (any future expiry / CVC) → back at /bookings/<id>/?stripe=success
# info flash shown; booking still PENDING + stripe_session_id set (CONFIRMED comes in US-25)
```

---

## Task 7: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md`**

- `Done` → add US-24; M3 count → 8/11
- `Ready (DoR ✅)` → US-25 (Stripe webhook + idempotency) — **brainstorm-required** per m3_planning

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-24 done — Stripe Checkout integration shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-21-stripe-checkout
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-24) / DoD / Test plan / Out of scope (webhook US-25, refund US-27).

---

## Self-Review (wykonane)

**Spec coverage:** §3 payments → Task 2. §4 service refactor + start_checkout → Task 3 Steps 4. §5 views (create refactor / checkout / detail) → Tasks 3/4/5. §6 URL → Task 4 Step 4. §7 template + config → Task 4 Step 5 / Task 1. §8 tests → Tasks 2-5 (conftest fixture, payments 3, service create+TestStartCheckout, create-view 2 changed + failure, checkout-view 6, detail 3). §9 DoD → covered. §10 risks: #1 churn → Task 3 explicitly lists removed/changed tests; #4 mypy session.url → Task 2/6 notes; #5 mypy user lookup → Task 4 note.

**Placeholder scan:** no TBD/TODO; every step has full code/command. Task 3 Step 1 uses prose "change/delete" directives for the existing file edits (with exact lines), not placeholders.

**Type consistency:** `create_checkout_session(booking) -> (str, str)` (Task 2) consumed by `start_checkout` (Task 3); `start_checkout(*, booking) -> str` consumed by both views (Tasks 3, 4); `create_booking(...) -> Booking` (Task 3) consumed by create view. `booking:checkout` URL name consistent (urls, checkout tests, template, detail test). `mock_checkout_session` fixture (`.url`/`.id`/`.side_effect`) used consistently across payments + booking Stripe tests. `stripe.error.StripeError`/`APIConnectionError` consistent.
