# US-34 — Admin/staff write API (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-34 — Admin/staff write API
**Branch:** `feat/FR-19-admin-api`
**FR refs:** FR-19 (REST API staff write), §4 (endpoint map), §8 (per-app `api/` structure)
**Date:** 2026-05-25
**Type:** plan-directly (M) — `ModelViewSet` CRUD + image uploads + a manual-refund action.
**Predecessor:** US-29..US-33 ✅ merged.

---

## 1. Goal

Staff-only write API under `/api/v1/admin/` for the catalog resources (full CRUD) and a
restricted bookings endpoint (manage + manual refund). `IsAdminUser` throughout.

**Definition of done (smoke):**
1. `POST/PUT/PATCH/DELETE /api/v1/admin/{movies,screenings,genres,halls,actors,directors}/`
   work for staff; non-staff → `403`, anon → `401`.
2. Image upload (`poster`/`photo`) via multipart: valid JPG/PNG/WebP ≤ 5MB → accepted;
   wrong format or > 5MB → `400`.
3. `GET /api/v1/admin/bookings/` (all), `PATCH …/<id>/` (status), `POST …/<id>/refund/`
   (manual refund of a CONFIRMED booking). No create/delete on bookings.

## 2. Scope boundary

**In scope:** admin CRUD viewsets + writable serializers, the image-upload validator, the
restricted bookings admin viewset + `refund_booking` service, the `/api/v1/admin/` router.

**Out of scope (later / deliberate):**
- Strict-mode CI schema gate → US-35; throttle-trip tests → US-36.
- **Raw create/delete on bookings** — bookings come from the user flow (`create_booking`
  lock + Stripe); admin gets list/retrieve/update + refund only (deliberate deviation from
  FR-19's literal "full CRUD" for bookings).
- No change to the public read API (US-31) or the user booking API (US-32).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Layout | Separate `apps/<app>/api/admin.py` + `admin_urls.py` per app; mounted `path("admin/", include(...))`. Keeps public read viewsets focused. |
| Permission | `rest_framework.permissions.IsAdminUser` (`is_staff=True`) on every admin viewset. |
| Bookings admin | **Restricted**: list/retrieve/`partial_update` (status) + `refund` action; **no create/delete**. |
| Manual refund | New `refund_booking` service — **bypasses** `can_be_cancelled()` (FR-19 "override automatu"); distinct from `cancel_booking`. |
| Parsers | `MultiPartParser` is already a DRF default (US-29 didn't override) — no per-view wiring. |
| Image validation | Shared `validate_image_upload` — size ≤ 5MB (checked first), then Pillow format ∈ {JPEG, PNG, WEBP}. |

## 4. Cinema admin (`apps/cinema/api/admin.py`)

`class AdminViewSet(viewsets.ModelViewSet): permission_classes = [IsAdminUser]` — shared base.

**Serializers:**
- Reuse the public `GenreSerializer` (`id, name`) and `HallSerializer`
  (`id, name, description, capacity`) — already plain writable ModelSerializers, no images.
- `AdminMovieSerializer(ModelSerializer)` — `fields = ("id", "title", "description",
  "release_date", "duration_minutes", "poster", "trailer_url", "genres", "actors",
  "directors")`; `genres`/`actors`/`directors` default to writable
  `PrimaryKeyRelatedField(many=True)`; `poster = serializers.ImageField(required=False,
  validators=[validate_image_upload])`.
- `AdminScreeningSerializer(ModelSerializer)` — `fields = ("id", "movie", "hall",
  "start_time", "price")`; `movie`/`hall` writable PK.
- `AdminActorSerializer(ActorSerializer)` / `AdminDirectorSerializer(DirectorSerializer)` —
  subclass the public serializer, override `photo = serializers.ImageField(required=False,
  validators=[validate_image_upload])`.

**ViewSets** (all `AdminViewSet` subclasses, full CRUD):
- `AdminGenreViewSet` (`Genre.objects.all()`, `GenreSerializer`).
- `AdminHallViewSet` (`Hall.objects.all()`, `HallSerializer`).
- `AdminActorViewSet` (`Actor.objects.all()`, `AdminActorSerializer`).
- `AdminDirectorViewSet` (`Director.objects.all()`, `AdminDirectorSerializer`).
- `AdminMovieViewSet` (`Movie.objects.prefetch_related("genres","actors","directors")`,
  `AdminMovieSerializer`).
- `AdminScreeningViewSet` (`Screening.objects.select_related("movie","hall")`,
  `AdminScreeningSerializer`).

## 5. Image validator (`apps/cinema/api/validators.py`)

```python
from PIL import Image
from rest_framework import serializers

MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(value):
    if value.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError("Image must be 5MB or smaller.")
    try:
        image = Image.open(value)
        fmt = image.format
    except Exception as exc:  # not a readable image
        raise serializers.ValidationError("Upload a valid image.") from exc
    finally:
        value.seek(0)
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise serializers.ValidationError("Image must be JPEG, PNG, or WebP.")
```

Size is checked **before** opening with Pillow, so an oversized file fails fast (and is
unit-testable without generating a multi-MB valid image). `value.seek(0)` resets the file
pointer after Pillow reads it, so the subsequent save isn't truncated.

## 6. Booking admin (`apps/booking/api/admin.py`)

- `AdminBookingSerializer(ModelSerializer)` — `fields = ("id", "user", "screening",
  "seats_count", "status", "total_price", "created_at", "expires_at", "refund_id",
  "refunded_at")`; `read_only_fields` = everything **except `status`** (admin edits status
  via PATCH); `total_price = DecimalField(max_digits=8, decimal_places=2, read_only=True)`.
- `AdminBookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
  mixins.UpdateModelMixin, viewsets.GenericViewSet)` — `permission_classes = [IsAdminUser]`,
  `queryset = Booking.objects.select_related("user", "screening__movie")`,
  `serializer_class = AdminBookingSerializer`. No create/destroy mixins.
- **`refund` `@action(detail=True, methods=["post"])`** (`@extend_schema(request=None,
  responses=AdminBookingSerializer)`):
  ```
  booking = self.get_object()
  try:
      updated = refund_booking(booking=booking)
  except BookingNotRefundableError as exc:
      return Response({"detail": str(exc)}, status=409)
  except (RefundError, stripe.StripeError) as exc:
      return Response({"detail": str(exc)}, status=502)
  return Response(AdminBookingSerializer(updated).data)
  ```

## 7. New service `apps/booking/services.py::refund_booking(*, booking) -> Booking`

```python
class BookingNotRefundableError(BookingError):
    def __init__(self) -> None:
        super().__init__("Tej rezerwacji nie można zwrócić.")


def refund_booking(*, booking: Booking) -> Booking:
    """Admin manual refund (FR-19) — overrides the auto cancel rules.

    Unlike cancel_booking, no can_be_cancelled() time check: an admin can refund a
    CONFIRMED booking regardless of how close the screening is. Refund runs inside the
    transaction before the status flips, so a Stripe failure rolls back (never CANCELLED
    without a refund).
    """
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if locked.status != BookingStatus.CONFIRMED or not locked.stripe_payment_intent_id:
            raise BookingNotRefundableError()
        try:
            refund_id = create_refund(locked)
        except stripe.StripeError as exc:
            raise RefundError() from exc
        locked.refund_id = refund_id
        locked.refunded_at = timezone.now()
        locked.status = BookingStatus.CANCELLED
        locked.save(update_fields=["status", "refund_id", "refunded_at"])
    return locked
```

Reuses `create_refund` (US-24, static idempotency key — a retry refunds at most once).
`expires_at` is already `None` on a CONFIRMED booking, so it's not in `update_fields`.

## 8. URLs

`apps/cinema/api/admin_urls.py` — `SimpleRouter`, register `movies, screenings, genres,
halls, actors, directors` (Admin* viewsets). `apps/booking/api/admin_urls.py` —
`SimpleRouter`, `register("bookings", AdminBookingViewSet, basename="admin-booking")`
(explicit basename — avoids colliding with the public `booking` basename from US-32).
`settings/api_urls.py`:
```python
    path("admin/", include("apps.cinema.api.admin_urls")),
    path("admin/", include("apps.booking.api.admin_urls")),
```
→ `/api/v1/admin/movies/`, …, `/api/v1/admin/bookings/`, `/api/v1/admin/bookings/<id>/refund/`.

## 9. OpenAPI

Admin viewsets are `ModelViewSet`s with concrete serializers → drf-spectacular documents
them (image fields render as binary). `@extend_schema` on the `refund` action documents
its `AdminBookingSerializer` response. Strict gate stays US-35.

## 10. Testing

**`tests/cinema/test_api_admin.py`** (`api_client`/`auth_client` + factories):
- **permissions** — anon → 401; authed non-staff → 403; staff → 200/201 on every resource.
- **CRUD** — create a genre; PATCH a movie's `genres` (PK list); create + delete a screening.
- **image upload** — POST a movie (multipart) with a small valid PNG → 201, `poster` set;
  POST with a valid GIF → 400 (format); (oversized covered by the validator unit test).
- **validator unit test** (`tests/cinema/test_image_validator.py` or in the admin test) —
  `validate_image_upload` raises on a 6MB `SimpleUploadedFile` (size-first) and on a GIF;
  passes a small PNG. Uses an in-memory PIL image helper.

**`tests/booking/test_api_admin.py`**:
- staff lists all bookings (incl. other users'); PATCH `status`; `POST …/refund/` on a
  CONFIRMED booking (`mock_refund`) → 200 CANCELLED + `refund_id` set; refund on a PENDING
  booking → 409; create (POST collection) → 405; delete → 405; non-staff → 403.

Image-test helper (in-memory):
```python
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

def image_upload(name="poster.png", fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type=f"image/{fmt.lower()}")
```

## 11. Coverage / migration

New `apps/cinema/api/{admin,validators}.py` + `apps/booking/api/admin.py` +
`refund_booking` are real code → covered by §10. Threshold ≥ 80% maintained.
**No migration** (no model changes).

## 12. Risks

1. **`refund_booking` vs `cancel_booking`** — separate paths by design: admin refund skips
   the `can_be_cancelled()` 1h rule; `RefundError`/`BookingNotRefundableError` ordering in
   the action maps to 502/409.
2. **Pillow file pointer** — `value.seek(0)` after `Image.open` or the saved file is empty.
3. **basename collision** — `admin-booking` explicit basename vs public `booking`.
4. **M2M write N+1 in admin list** — `AdminMovieViewSet` prefetches genres/actors/directors.
5. **mypy** — `get_object`/`@action` returns; the validator is plain (no DRF generics).
6. **drf-spectacular + ImageField/multipart** — should document cleanly; verify no new
   warnings now (US-35 enforces strict).

## 13. Build order (for the plan)

1. Image validator + its unit test.
2. Cinema admin serializers + viewsets + `admin_urls.py` + mount; cinema admin tests (perms, CRUD, upload).
3. `refund_booking` service + test.
4. Booking admin serializer + viewset + `admin_urls.py` + mount; booking admin tests.
5. Quality gate (pytest cov ≥ 80%, ruff, mypy).

The first branch commit folds in the `backlog.md` board update (US-33 → Done, US-34 → In
Progress) made at US-34 start.
