# KinoMania — Wymagania Funkcjonalne

**Wersja:** 3.0
**Data:** 2026-05-04
**Cel dokumentu:** Specyfikacja wymagań funkcjonalnych przeznaczona do implementacji. Wersja 3.0 dodaje równoległe REST API (DRF) oraz integrację płatności Stripe (sandbox).

---

## 1. Wprowadzenie

### 1.1 Cel projektu
KinoMania to serwis internetowy dla kina, umożliwiający użytkownikom przeglądanie repertuaru, poznawanie szczegółów filmów oraz rezerwację biletów na seanse. System wspiera również administrację repertuarem i obsługę użytkowników. Serwis jest wielojęzyczny (polski i angielski).

### 1.2 Założenia technologiczne
- **Backend:** Python **3.13**, Django 6.x
- **REST API:** Django REST Framework + `djangorestframework-simplejwt` (JWT) + `drf-spectacular` (OpenAPI 3.1, Swagger UI, ReDoc)
- **Płatności:** **Stripe** (`stripe` Python SDK) w trybie **Checkout (hosted)** — całość projektu na kluczach test (sandbox); webhooki lokalnie przez Stripe CLI
- **Baza danych:** PostgreSQL 16 via `docker-compose` (dev + prod)
- **Frontend:** Django Templates + **Bootstrap 5**
- **Media:** Django `ImageField` + Pillow
- **Autoryzacja:** `django.contrib.auth` z **niestandardowym modelem User** (logowanie przez email, brak pola `username`); JWT (access + refresh) dla API
- **Internacjonalizacja:** `django.utils.translation` (`gettext_lazy`), `LocaleMiddleware`, język polski (domyślny) + angielski
- **Panel admina:** Django Admin (z `search_fields`, `list_filter`, `inlines`, custom metody w `list_display`)
- **Generowanie danych testowych:** `Faker` + własna komenda management `seed_db`
- **Testy:** `pytest-django` + `factory_boy` + `pytest-cov` (coverage threshold **80%**) — modele, widoki, formularze, logika biznesowa, webhooki, race conditions
- **Code quality:** `ruff` (lint+format) + `mypy` (django-stubs, drf-stubs) + `pre-commit` + GitHub Actions CI
- **Konfiguracja:** sekrety w `.env` (`django-environ`), `.env.example` w repo
- **Środowisko developerskie:** PyCharm + Poetry (zarządzanie zależnościami) + Docker Compose (Postgres) + Stripe CLI (webhooki lokalnie)

### 1.3 Konwencje nazewnicze
- **Kod źródłowy (modele, pola, klasy, widoki, URLe, zmienne, komentarze):** wyłącznie **angielski** (snake_case dla pól i funkcji, PascalCase dla klas).
- **Treści dla użytkownika końcowego (etykiety formularzy, treść szablonów, komunikaty, `verbose_name`, `help_text`, `choices` labels):** opakowane w `gettext_lazy("...")` i tłumaczone na PL/EN.
- **Dokumentacja techniczna i komentarze w kodzie:** angielski.
- **Ten dokument wymagań:** polski.

---

## 2. Aktorzy systemu

| Aktor | Opis | Logowanie | Uprawnienia |
|---|---|---|---|
| **Gość (anonim)** | Niezalogowany użytkownik | — | Przeglądanie repertuaru, szczegółów filmów, harmonogramu seansów |
| **Użytkownik zarejestrowany** | Zalogowany użytkownik | **email + hasło** | Wszystko co Gość + rezerwacje, panel rezerwacji, anulowanie |
| **Administrator (staff)** | Pracownik kina | email + hasło | Pełen dostęp do panelu Django Admin |

---

## 3. Modele danych

> **Wszystkie pola modelowe mają zdefiniowane `verbose_name = _("...")` z `gettext_lazy` dla tłumaczeń.** Przykłady tłumaczeń w sekcji 3.X są skrócone.

### 3.1 `User` (custom user model — aplikacja `accounts`)

**Wymóg krytyczny:** zdefiniowany **przed pierwszą migracją**. W `settings.py` ustawione `AUTH_USER_MODEL = "accounts.User"`.

Model dziedziczy po `AbstractBaseUser` + `PermissionsMixin`. Pola:

| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `email` | EmailField | **unique=True**, not null — pole loginu |
| `first_name` | CharField(150) | blank=True |
| `last_name` | CharField(150) | blank=True |
| `is_active` | BooleanField | default=True |
| `is_staff` | BooleanField | default=False |
| `date_joined` | DateTimeField | auto_now_add=True |

**Konfiguracja modelu:**
```python
USERNAME_FIELD = "email"
REQUIRED_FIELDS = []  # pola wymagane przy createsuperuser oprócz USERNAME_FIELD i password
objects = UserManager()
```

**`UserManager` (custom, w tym samym pliku):**
- `create_user(email, password=None, **extra_fields)` — waliduje obecność emaila (`ValueError` jeśli pusty), normalizuje (`self.normalize_email`), ustawia hasło.
- `create_superuser(email, password=None, **extra_fields)` — wymusza `is_staff=True`, `is_superuser=True`, `is_active=True`.

**`__str__`:** zwraca `self.email`.

**Uwaga:** standardowy `ModelBackend` Django wystarczy — przy `USERNAME_FIELD = "email"` Django automatycznie loguje przez email. Nie ma potrzeby pisania custom backendu.

### 3.2 `Genre`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `name` | CharField(50) | unique, not null |

### 3.3 `Actor`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `full_name` | CharField(150) | not null |
| `photo` | ImageField | upload_to="actors/", blank=True |
| `biography` | TextField | blank=True |

### 3.4 `Director`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `full_name` | CharField(150) | not null |
| `photo` | ImageField | upload_to="directors/", blank=True |
| `biography` | TextField | blank=True |

### 3.5 `Hall`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `name` | CharField(50) | unique |
| `capacity` | PositiveIntegerField | default=100, validator: > 0 |

### 3.6 `Movie`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `title` | CharField(200) | not null |
| `description` | TextField | not null |
| `release_date` | DateField | not null |
| `duration_minutes` | PositiveIntegerField | > 0 |
| `poster` | ImageField | upload_to="posters/", blank=True |
| `trailer_url` | URLField | blank=True (np. YouTube) |
| `genres` | ManyToManyField → Genre | related_name="movies" |
| `actors` | ManyToManyField → Actor | related_name="movies" |
| `directors` | ManyToManyField → Director | related_name="movies" |

**Metody:** `get_absolute_url()`, `__str__` zwraca `title`.

### 3.7 `Screening`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `movie` | ForeignKey → Movie | on_delete=CASCADE, related_name="screenings" |
| `hall` | ForeignKey → Hall | on_delete=PROTECT |
| `start_time` | DateTimeField | not null |
| `price` | DecimalField(6, 2) | > 0 |

**Metody:**
- `booked_seats_count()` — suma `seats_count` z bookingów o statusie `CONFIRMED`.
- `available_seats_count()` — `hall.capacity - booked_seats_count()`.
- `is_available()` — zwraca `True` jeśli `start_time > now()` i są wolne miejsca.
- `is_in_past()` — `start_time <= now()`.

### 3.8 `Booking`
| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `user` | ForeignKey → User (`settings.AUTH_USER_MODEL`) | on_delete=CASCADE, related_name="bookings" |
| `screening` | ForeignKey → Screening | on_delete=CASCADE, related_name="bookings" |
| `seats_count` | PositiveIntegerField | >= 1, <= 10 |
| `status` | CharField(choices) | PENDING / CONFIRMED / CANCELLED, **default=PENDING** |
| `expires_at` | DateTimeField | null=True; ustawiane przy tworzeniu PENDING (`now + 15 min`) |
| `stripe_session_id` | CharField(255) | blank=True; ID `Checkout Session` |
| `stripe_payment_intent_id` | CharField(255) | blank=True; ID `PaymentIntent` po sukcesie |
| `refund_id` | CharField(255) | blank=True; ID `Refund` po anulowaniu CONFIRMED |
| `refunded_at` | DateTimeField | null=True; znacznik czasu refundu |
| `created_at` | DateTimeField | auto_now_add=True |

**Choices (TextChoices z tłumaczeniami):**
```python
class BookingStatus(models.TextChoices):
    PENDING = "PENDING", _("Oczekująca")       # zarezerwowane miejsca, czeka na płatność
    CONFIRMED = "CONFIRMED", _("Potwierdzona") # płatność zakończona sukcesem (webhook Stripe)
    CANCELLED = "CANCELLED", _("Anulowana")    # anulowana przez usera lub przez auto-expiration
```

**Walidacja w `clean()`:**
- `seats_count` ≤ liczba dostępnych miejsc (z uwzględnieniem siebie przy edycji; PENDING z `expires_at > now()` liczone jako zajęte).
- Nie można rezerwować na seans w przeszłości.

**Property:** `total_price` — `seats_count * screening.price`.

**Cykl życia:**
1. Utworzenie → status `PENDING`, `expires_at = now + 15 min`, redirect/zwrot URL Stripe Checkout.
2. Webhook `checkout.session.completed` → status `CONFIRMED`, zapis `stripe_payment_intent_id`.
3. Webhook `checkout.session.expired` lub przekroczenie `expires_at` (komenda `expire_pending_bookings`) → status `CANCELLED`.
4. Anulowanie `CONFIRMED` przez usera (FR-10) → Stripe Refund → status `CANCELLED`, zapis `refund_id` i `refunded_at`.

### 3.9 `StripeEvent` (idempotency log — aplikacja `payments`)

Persystowany rejestr każdego odebranego webhooka Stripe — gwarantuje, że ten sam event nigdy nie zmieni stanu domeny dwukrotnie (Stripe retry'uje webhooki przy błędach 5xx).

| Pole | Typ | Ograniczenia |
|---|---|---|
| `id` | AutoField | PK |
| `event_id` | CharField(255) | **unique=True**, not null — Stripe `Event.id` (np. `evt_1A...`) |
| `event_type` | CharField(100) | not null — np. `checkout.session.completed` |
| `payload` | JSONField | not null — pełny event JSON |
| `received_at` | DateTimeField | auto_now_add=True |
| `processed_at` | DateTimeField | null=True; ustawiane po pomyślnej obsłudze |

**Reguła obsługi:** webhook handler najpierw `get_or_create(event_id=...)` — jeśli rekord istnieje, zwracamy `200 OK` bez ponownego wykonywania logiki; jeśli nowy, wykonujemy zmianę stanu i ustawiamy `processed_at`.

---

## 4. Wymagania funkcjonalne (Functional Requirements)

> URLe podane poniżej to ścieżki bazowe. Język UI sterowany jest przez `LocaleMiddleware` (sesja/cookie). Polski jest językiem domyślnym; angielski dostępny przez przełącznik w navbarze (FR-15).

### FR-01 — Strona główna / Repertuar
**URL:** `/` (alias do `/movies/`)
**Akceptacja:**
- Wyświetlane filmy, które mają co najmniej jeden `Screening` z `start_time >= today`.
- Karta filmu: poster (lub placeholder), `title`, gatunki (badge), data najbliższego seansu, przycisk „Szczegóły" / „Details".
- Paginacja po 12 filmów.
- Dostępne dla wszystkich.

### FR-02 — Filtrowanie i wyszukiwanie
**Akceptacja:**
- Pole tekstowe — search po `title` (icontains).
- Filtr po `Genre` (dropdown lub multiselect).
- Filtr po dacie seansu (date picker).
- Parametry przez GET: `?q=...&genre=...&date=...`.

### FR-03 — Strona szczegółów filmu
**URL:** `/movies/<int:pk>/`
**Akceptacja:**
- Sekcje: poster, title, description, release_date, duration_minutes, lista gatunków, lista directors (ze zdjęciami), lista actors (galeria/karuzela ze zdjęciami).
- Osadzony zwiastun (`trailer_url`) — jeśli to YouTube, embed iframe.
- Sekcja „Najbliższe seanse" / „Upcoming screenings": lista przyszłych `Screening` (data, godzina, hall, price, available_seats_count, przycisk „Zarezerwuj" / „Book").
- Brak seansów → komunikat tłumaczony.

### FR-04 — Harmonogram seansów na dany dzień
**URL:** `/screenings/?date=YYYY-MM-DD` (default: dziś)
**Akceptacja:**
- Date picker (dziś do +30 dni).
- Lista posortowana po `start_time`, pogrupowana po filmie.
- Każdy seans: tytuł (link do FR-03), godzina, hall, price, dostępne miejsca, przycisk rezerwacji.

### FR-05 — Rejestracja użytkownika
**URL:** `/accounts/register/`
**Akceptacja:**
- Formularz pól: `email`, `password1`, `password2`, opcjonalnie `first_name`, `last_name`. **Brak pola username.**
- Walidacja:
  - `email` — wymagany, format prawidłowy, **unikalny w systemie**.
  - `password1 == password2`, zgodność z `AUTH_PASSWORD_VALIDATORS`.
- Po sukcesie → automatyczne logowanie i redirect na `/`.
- Komunikaty błędów przy polach (tłumaczone).

### FR-06 — Logowanie i wylogowanie
**URLe:** `/accounts/login/`, `/accounts/logout/`
**Akceptacja:**
- Formularz logowania zawiera pola **`email`** i **`password`** (NIE username).
- Implementacja: custom `EmailAuthenticationForm` dziedzicząca po `AuthenticationForm`, z polem `username` przemianowanym/zastąpionym `email` (label = `_("Email")`, widget `EmailInput`).
- Po zalogowaniu → redirect na `?next=` lub `/`.
- Po wylogowaniu → redirect na `/`.
- Standardowy `LogoutView`.

### FR-07 — Rezerwacja biletów
**URL:** `/screenings/<int:pk>/book/`
**Akceptacja:**
- **Wymaga logowania** (`LoginRequiredMixin` / `@login_required`).
- Formularz: pole `seats_count` (1–10), wyświetlane podsumowanie (tytuł, godzina, hall, cena za miejsce, łączna cena obliczana JS-em, available_seats_count).
- Walidacja serwerowa:
  - `seats_count <= screening.available_seats_count()` — w przeciwnym razie błąd z liczbą dostępnych (uwzględnia PENDING z `expires_at > now()` jako zajęte).
  - `screening.start_time > now()` — w przeciwnym razie błąd „Seans już się rozpoczął".
- Operacja w `transaction.atomic()` z `Screening.objects.select_for_update().get(pk=...)` — zabezpieczenie przed race condition.
- **Flow z Stripe Checkout:**
  1. Utworzenie `Booking` ze statusem `PENDING`, `expires_at = now + 15 min` — miejsca są zarezerwowane (liczą się do `available_seats_count`).
  2. Utworzenie Stripe `Checkout Session` (idempotency key = `booking-<id>`), zapis `stripe_session_id`.
  3. Redirect (web) lub zwrot `{checkout_url, session_id}` (API) — patrz FR-21.
  4. Po pomyślnej płatności webhook (FR-22) zmienia status na `CONFIRMED`.
  5. Brak płatności w 15 min → `expire_pending_bookings` (FR-23) zmienia status na `CANCELLED`.

### FR-08 — Strona potwierdzenia rezerwacji
**URL:** `/bookings/<int:pk>/`
**Akceptacja:**
- Dostęp tylko dla właściciela (`booking.user == request.user`) lub staffu. Inny user → HTTP 403.
- Pokazuje: numer, tytuł filmu, datę i godzinę seansu, hall, seats_count, total_price, status.

### FR-09 — Panel użytkownika: lista rezerwacji
**URL:** `/my-bookings/`
**Akceptacja:**
- Wymaga logowania.
- Lista bookingów zalogowanego usera, sortowana malejąco po `created_at`.
- Dwie sekcje (taby): „Nadchodzące" (`screening.start_time >= now()`) i „Historia".
- Każdy element: tytuł, data seansu, hall, seats_count, status, total_price, przycisk „Anuluj" (jeśli reguła z FR-10 spełniona).

### FR-10 — Anulowanie rezerwacji
**URL:** `POST /bookings/<int:pk>/cancel/`
**Akceptacja:**
- Wymaga logowania, tylko właściciel.
- Możliwe gdy `screening.start_time > now() + timedelta(hours=1)`.
- Status zmieniany na `CANCELLED` (rekord pozostaje — historia).
- Po sukcesie → flash message + redirect na `/my-bookings/`.

### FR-11 — Rozbudowany panel administracyjny
**URL:** `/admin/`

**`MovieAdmin`:**
- `list_display = ("title", "release_date", "poster_thumbnail", "screenings_count", "genres_list")`
- `search_fields = ("title", "description", "directors__full_name")`
- `list_filter = ("genres", "release_date")`
- `filter_horizontal = ("genres", "actors", "directors")`
- `date_hierarchy = "release_date"`
- `inlines = [ScreeningInline]`
- Custom: `poster_thumbnail`, `screenings_count`, `genres_list`.

**`ScreeningAdmin`:**
- `list_display = ("movie", "start_time", "hall", "price", "available_seats_display", "booked_seats_display")`
- `list_filter = ("hall", "movie", "start_time")`
- `search_fields = ("movie__title",)`
- `date_hierarchy = "start_time"`
- `inlines = [BookingInline]`
- Custom: kolorowe badge dla dostępności (zielony/żółty/czerwony).

**`BookingAdmin`:**
- `list_display = ("id", "user", "screening", "seats_count", "status", "total_price_display", "created_at")`
- `list_filter = ("status", "screening__movie", "created_at")`
- `search_fields = ("user__email", "screening__movie__title")`
- `readonly_fields = ("created_at",)`
- `list_editable = ("status",)`

**`UserAdmin` (custom dla naszego User):**
- Dziedziczy po `BaseUserAdmin`, ale dostosowany do braku `username`.
- `list_display = ("email", "first_name", "last_name", "is_staff", "date_joined")`
- `search_fields = ("email", "first_name", "last_name")`
- `list_filter = ("is_staff", "is_active")`
- `ordering = ("email",)`
- `fieldsets` i `add_fieldsets` przeprojektowane: pole logowania to `email`, nie `username`.

**`ActorAdmin` / `DirectorAdmin`:**
- `list_display = ("full_name", "photo_thumbnail", "movies_count")`
- `search_fields = ("full_name",)`

**`HallAdmin`:**
- `list_display = ("name", "capacity", "screenings_count")`
- `inlines = [ScreeningInline]`

**`GenreAdmin`:**
- `list_display = ("name", "movies_count")`
- `search_fields = ("name",)`

**Inlines:**
- `ScreeningInline(admin.TabularInline)` — `extra = 1`.
- `BookingInline(admin.TabularInline)` — `extra = 0`, readonly `(user, seats_count, created_at)`.

### FR-12 — Obsługa błędów i ochrona dostępu
- Custom szablony 403, 404, 500 (tłumaczone).
- Wszystkie chronione widoki — `LoginRequiredMixin` lub `@login_required`.
- Próba dostępu do cudzego bookingu → 403.
- Nieistniejący zasób → 404.
- Komunikaty walidacji wyświetlane przy polach.
- `django.contrib.messages` do flash-ów.

### FR-13 — Komenda management `seed_db`
**Lokalizacja:** `cinema/management/commands/seed_db.py`
**Wywołanie:** `python manage.py seed_db [--flush] [--movies=N] [--screenings=N] [--users=N] [--bookings=N]`

**Akceptacja:**
- Dziedziczy po `BaseCommand`.
- **Defaulty:** `--movies=20`, `--screenings=100`, `--users=10`, `--bookings=30`.
- `--flush` — czyści istniejące dane (oprócz superuserów) w odpowiedniej kolejności (bookings → screenings → movies → reszta).
- **Generowane dane:**
  - **Genres:** stała lista 9 gatunków (Action, Comedy, Drama, Horror, Sci-Fi, Animation, Thriller, Romance, Documentary).
  - **Halls:** 3–5 sal, capacity 50–200.
  - **Actors / Directors:** Faker `name()` (`locale="pl_PL"`), biography z `paragraph()`.
  - **Movies:** title z `catch_phrase()`, description `paragraph(nb_sentences=5)`, release_date w zakresie ostatnich 2 lat, duration_minutes 80–180, losowo 1–3 genres / 3–8 actors / 1–2 directors.
  - **Screenings:** losowy movie + hall, start_time od -7 do +30 dni, price 25.00–55.00.
  - **Users:** email z Fakera, hasło `test1234` (tylko dev).
  - **Bookings:** losowy user + screening (z dostępnymi miejscami), seats_count 1–4, **85% CONFIRMED / 5% PENDING (z `expires_at` losowo w przeszłości lub przyszłości — do testowania `expire_pending_bookings`) / 10% CANCELLED**.
  - **StripeEvent:** generowane wpisy dla CONFIRMED bookingów (event_id = `evt_seed_<uuid>`, event_type = `checkout.session.completed`, payload = minimalny mock JSON z `client_reference_id = booking.id`).
- **Bezpieczeństwo:** komenda odmawia uruchomienia gdy `DEBUG=False`, chyba że dodano flagę `--force` (informacyjny `self.stderr.write` z ostrzeżeniem).
- **Output:** progress bar lub komunikaty `self.style.SUCCESS`, podsumowanie końcowe.

### FR-14 — Testy jednostkowe i integracyjne
**Stack:** `pytest-django` + `factory_boy` + `pytest-cov` + `pytest-mock`. Coverage threshold globalne **80%** (egzekwowane przez CI).
**Lokalizacja:** `accounts/tests/`, `cinema/tests/`, `payments/tests/`
**Wywołanie:** `poetry run pytest --cov` (lokalnie) / `poetry run pytest --cov-fail-under=80` (CI)
**Konwencja:** funkcyjne testy `def test_…(db, …)` zamiast klas; factories per app w `<app>/factories.py`; Stripe mockowany przez `pytest-mock` + helpers fixture w `conftest.py`.

**`accounts/tests/test_models.py`:**
- `test_create_user_with_email` — utworzenie usera z emailem i hasłem.
- `test_create_user_without_email_raises` — pusty email → `ValueError`.
- `test_create_superuser_sets_flags` — `is_staff` i `is_superuser` = True.
- `test_email_is_username_field` — sprawdzenie `USERNAME_FIELD == "email"`.
- `test_email_unique` — drugi user z tym samym emailem → `IntegrityError`.

**`accounts/tests/test_views.py`:**
- `test_register_with_valid_email_creates_user` — POST z poprawnymi danymi → user utworzony, zalogowany.
- `test_register_rejects_duplicate_email`.
- `test_login_with_email_works` — POST email + password → sesja zalogowana.
- `test_login_with_wrong_password_fails`.

**`cinema/tests/test_models.py`:**
- `test_movie_str_returns_title`.
- `test_screening_available_seats_count` — sala 100, booking 30 → expected 70.
- `test_screening_is_available_returns_false_for_past`.
- `test_booking_validation_too_many_seats` → `ValidationError`.
- `test_booking_validation_screening_in_past` → `ValidationError`.
- `test_movie_m2m_relations` — przypisanie i odczyt z obu stron.

**`cinema/tests/test_views.py`:**
- `test_movie_list_returns_200`.
- `test_movie_detail_returns_200`, nieistniejący → 404.
- `test_booking_requires_login` → redirect 302.
- `test_logged_user_can_book` — POST → utworzenie obiektu, redirect na confirmation.
- `test_my_bookings_shows_only_own` — user A 2 bookingi, user B 1; A widzi tylko swoje 2.
- `test_403_on_others_booking_detail`.

**`cinema/tests/test_forms.py`:**
- `test_booking_form_rejects_zero_seats`.
- `test_booking_form_rejects_above_available`.

**`cinema/tests/test_business_logic.py`:**
- `test_race_condition_on_last_seat` — dwie równoczesne rezerwacje, tylko jedna sukces.
- `test_cancel_allowed_more_than_hour_before`.
- `test_cancel_blocked_within_hour`.

**`payments/tests/test_webhook.py`:**
- `test_webhook_rejects_invalid_signature` — wywołanie z nieprawidłowym `Stripe-Signature` → HTTP 400.
- `test_webhook_accepts_valid_signature` — poprawnie podpisany event → HTTP 200, log `StripeEvent` utworzony.
- `test_webhook_idempotent_on_duplicate_event` — ten sam `event_id` 2× → tylko 1 zmiana stanu Booking, 2 odpowiedzi 200 OK.
- `test_checkout_session_completed_confirms_booking` — webhook z eventem `checkout.session.completed` → Booking.status PENDING → CONFIRMED, zapisany `stripe_payment_intent_id`.
- `test_checkout_session_expired_cancels_booking` — webhook z eventem `checkout.session.expired` → status PENDING → CANCELLED.

**`payments/tests/test_expire_command.py`:**
- `test_expire_pending_bookings_cancels_expired` — booking PENDING z `expires_at < now()` → CANCELLED po wywołaniu komendy.
- `test_expire_pending_bookings_skips_active_pending` — booking PENDING z `expires_at > now()` → bez zmian.
- `test_expire_pending_bookings_skips_confirmed` — booking CONFIRMED → bez zmian niezależnie od `expires_at`.

**`payments/tests/test_refund.py`:**
- `test_cancel_confirmed_booking_creates_stripe_refund` — anulowanie CONFIRMED bookingu → wywołanie `stripe.Refund.create` (mocked) z poprawnym `payment_intent`, zapis `refund_id` i `refunded_at`.
- `test_cancel_pending_booking_does_not_call_stripe` — anulowanie PENDING (jeszcze nie zapłacone) → bez wywołania Stripe API.

**`*/tests/test_api_*.py` (testy DRF):**
- Testy dla każdego endpointu API (auth, public, booking, admin) — happy path + permissions + walidacja.
- Testy throttli — N+1 zapytanie zwraca 429.
- Test OpenAPI schema — `/api/v1/schema/` zwraca poprawny YAML/JSON.

**Wymagania techniczne:**
- `factory_boy` factories per app (`UserFactory`, `MovieFactory`, `BookingFactory`, etc.) — w `<app>/factories.py`. Subfactories dla wariantów (`PendingBookingFactory`, `PastScreeningFactory`).
- Stripe API zawsze mockowane (`pytest-mock` patch na `stripe.checkout.Session.create`, `stripe.Refund.create`, `stripe.Webhook.construct_event`).
- Brak zewnętrznych zależności sieciowych.
- `pytest --reuse-db` — szybkie iteracje; `--create-db` przy zmianie migracji.
- `poetry run pytest --cov-fail-under=80` zwraca zielony output.

### FR-16 — REST API: autentykacja
**Bazowy URL:** `/api/v1/auth/`

**Endpointy:**
- `POST /api/v1/auth/register/` — rejestracja (analogicznie do FR-05; pola: `email`, `password`, opcjonalnie `first_name`, `last_name`); zwraca `{user, access, refresh}`.
- `POST /api/v1/auth/token/` — login (`email` + `password`); zwraca `{access, refresh}`.
- `POST /api/v1/auth/token/refresh/` — odświeżenie access tokenu; zwraca `{access}`.
- `GET /api/v1/auth/me/` — dane zalogowanego usera (`IsAuthenticated`).

**Akceptacja:**
- `djangorestframework-simplejwt` jako provider JWT; `JWTAuthentication` jako default DRF auth class (z `SessionAuthentication` jako fallback dla browsable API w trybie DEBUG).
- Czas życia: `access = 15 min`, `refresh = 7 dni` (konfigurowalne przez `.env`).
- Throttling: `auth` scope = 20 requestów/godzinę (anti-bruteforce na endpointach `/register/` i `/token/`).
- Walidacja siły hasła: `AUTH_PASSWORD_VALIDATORS` jak dla web (FR-05).
- Błędy walidacji w formacie DRF (`{"field": ["error1", "error2"]}`).

### FR-17 — REST API: publiczne read-only
**Bazowy URL:** `/api/v1/`

**Endpointy (wszystkie `IsAuthenticatedOrReadOnly` — anon dostają GET, mutacje wymagają loginu):**
- `GET /api/v1/movies/` — lista (paginacja 12, filtry `genre`, `release_date_after/before`, search po `title`).
- `GET /api/v1/movies/<id>/` — szczegóły z zagnieżdżonymi `genres`, `actors`, `directors`, `screenings` (najbliższe).
- `GET /api/v1/screenings/?date=YYYY-MM-DD` — harmonogram (filtr `date`, `movie`, `hall`).
- `GET /api/v1/screenings/<id>/` — szczegóły seansu z `available_seats_count`.
- `GET /api/v1/genres/`, `/halls/`, `/actors/`, `/directors/` — read-only listings (mutacje przez FR-19).

**Akceptacja:**
- Pagination: `PageNumberPagination`, page_size=12.
- Filtry: `django-filter` z `FilterSet` per ViewSet.
- Search: `SearchFilter` na `title`/`full_name`.
- Ordering: `OrderingFilter` (np. `?ordering=-release_date`).
- Throttling: `anon` 100/h, `user` 1000/h.

### FR-18 — REST API: rezerwacje
**Bazowy URL:** `/api/v1/bookings/`

**Endpointy (wszystkie `IsAuthenticated`, owner-only przez custom permission):**
- `GET /api/v1/bookings/` — lista bookingów zalogowanego usera (sortowana po `created_at desc`).
- `POST /api/v1/bookings/` — tworzenie nowego (analogicznie do FR-07: `screening_id`, `seats_count` → tworzy PENDING, zwraca booking + Stripe `checkout_url`).
- `GET /api/v1/bookings/<id>/` — szczegóły (403 jeśli nie owner i nie staff).
- `POST /api/v1/bookings/<id>/cancel/` — anulowanie (analogicznie do FR-10: refund jeśli CONFIRMED).
- `POST /api/v1/bookings/<id>/checkout/` — utworzenie nowej Stripe Session (np. po expired); zwraca `{checkout_url, session_id}`.

**Akceptacja:**
- Logika identyczna z web (FR-07, FR-08, FR-10) — wspólny serwis `cinema.services.bookings`.
- Transakcja `atomic()` + `select_for_update()` na Screening — taka sama ochrona przed race condition.
- Permissions: custom `IsBookingOwnerOrStaff` na detail/cancel/checkout.

### FR-19 — REST API: zapis dla staff (admin)
**Bazowe URL-e:** `/api/v1/admin/movies/`, `/admin/screenings/`, `/admin/genres/`, `/admin/halls/`, `/admin/actors/`, `/admin/directors/`, `/admin/bookings/`

**Akceptacja:**
- Wszystkie endpointy `IsAdminUser` (`is_staff=True`).
- Pełen CRUD (POST/PUT/PATCH/DELETE) na każdym zasobie z odpowiadającymi serializerami.
- ImageField uploads via multipart (`MultiPartParser`) — limit 5MB, format JPG/PNG/WebP.
- Custom action `POST /api/v1/admin/bookings/<id>/refund/` — manualny refund (override automatu z FR-24).

### FR-20 — REST API: dokumentacja OpenAPI
**Generator:** `drf-spectacular`.

**URL-e:**
- `GET /api/v1/schema/` — surowy OpenAPI 3.1 schema (YAML domyślnie, JSON via `?format=json`).
- `GET /api/v1/docs/` — Swagger UI.
- `GET /api/v1/redoc/` — ReDoc.

**Akceptacja:**
- `SPECTACULAR_SETTINGS` w `settings.py`: `TITLE = "KinoMania API"`, `VERSION = "1.0.0"`, `DESCRIPTION` z Markdown overview.
- Każdy ViewSet ma `@extend_schema` z opisem + przykładami request/response.
- Schemat zawiera definicje JWT auth (`bearerAuth` security scheme) — przycisk „Authorize" w Swagger UI działa.
- W CI: `pytest` weryfikuje, że `drf-spectacular` generuje schemę bez `Warnings` (strict mode).

### FR-21 — Stripe Checkout (web + API)
**Endpointy:**
- Web: `POST /bookings/<id>/checkout/` (CSRF-protected) → `redirect()` do `Checkout Session.url`.
- API: `POST /api/v1/bookings/<id>/checkout/` → JSON `{checkout_url, session_id}`.

**Akceptacja:**
- Tworzenie sesji w `payments.services.stripe.create_checkout_session(booking)`:
  - `mode = "payment"`, `currency = STRIPE_CURRENCY` (default `pln`), `payment_method_types = ["card"]`.
  - `line_items` — jedna pozycja z `unit_amount = int(booking.total_price * 100)` (grosze), `quantity = 1`, `name = f"Booking #{booking.id} — {booking.screening.movie.title}"`.
  - `client_reference_id = str(booking.id)` — wiązanie webhooka z bookingiem.
  - `success_url = <DOMAIN>/bookings/<id>/?stripe=success`, `cancel_url = <DOMAIN>/bookings/<id>/?stripe=cancelled`.
  - `idempotency_key = f"booking-{booking.id}-checkout"` — bezpieczne retry'e.
  - `expires_at = int((booking.expires_at).timestamp())` — Stripe sam zamyka sesję po expire.
- Zapis `Booking.stripe_session_id`.
- Tworzenie sesji wymaga `Booking.status == PENDING` — w przeciwnym razie HTTP 409.

### FR-22 — Stripe webhooks
**URL:** `POST /webhooks/stripe/` (CSRF-exempt; sygnatura Stripe weryfikuje autentyczność)

**Akceptacja:**
- Verify: `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)` — przy błędzie HTTP 400.
- Idempotency: `StripeEvent.objects.get_or_create(event_id=event.id, defaults={...})` — duplikaty skutkują HTTP 200 bez akcji.
- Obsługiwane eventy:
  - `checkout.session.completed` → `Booking.status = CONFIRMED`, zapis `stripe_payment_intent_id` z `event.data.object.payment_intent`.
  - `checkout.session.expired` → `Booking.status = CANCELLED`.
  - `payment_intent.payment_failed` → `Booking.status = CANCELLED` (po `client_reference_id` z `payment_intent.metadata`).
- Każda zmiana stanu w `transaction.atomic()` z `select_for_update()` na Booking.
- Po sukcesie: `StripeEvent.processed_at = timezone.now()`.
- Lokalny dev: `stripe listen --forward-to localhost:8000/webhooks/stripe/` — Stripe CLI publikuje testowy `whsec_…` skopiowany do `.env`.

### FR-23 — Auto-expiration PENDING bookings
**Komenda:** `poetry run python manage.py expire_pending_bookings [--dry-run]`

**Akceptacja:**
- Znajduje wszystkie `Booking` z `status = PENDING` i `expires_at < now()`.
- Dla każdego: `status = CANCELLED`, `expires_at` zostaje (audytowo).
- Output: ile bookingów zmieniono, suma zwolnionych miejsc.
- `--dry-run` — pokazuje co by zmieniło, bez `save()`.
- W produkcji wywoływane co 1 min przez cron systemowy / Celery beat (out of scope MVP — uruchamiane ręcznie w dev).
- Idempotentne — wielokrotne wywołanie nie zmienia już zaktualizowanych bookingów.

### FR-24 — Refund flow przy anulowaniu
**Trigger:** anulowanie `CONFIRMED` bookingu (web FR-10 lub API FR-18).

**Akceptacja:**
- Tylko jeśli `Booking.status == CONFIRMED` i `stripe_payment_intent_id` jest ustawione.
- `stripe.Refund.create(payment_intent=booking.stripe_payment_intent_id, idempotency_key=f"booking-{booking.id}-refund")` — przy błędzie Stripe (np. już zwrócone) → komunikat błędu, status nie zmienia się.
- Po sukcesie: `Booking.refund_id = refund.id`, `Booking.refunded_at = timezone.now()`, `Booking.status = CANCELLED`.
- `PENDING` anulowane bezpośrednio bez wywołania Stripe (jeszcze nie zapłacone).

### FR-15 — Internacjonalizacja (PL/EN)
**Akceptacja:**
- **Settings:**
  ```python
  LANGUAGE_CODE = "pl"
  LANGUAGES = [("pl", _("Polski")), ("en", _("English"))]
  LOCALE_PATHS = [BASE_DIR / "locale"]
  USE_I18N = True
  TIME_ZONE = "Europe/Warsaw"
  USE_TZ = True
  ```
- **Middleware:** `django.middleware.locale.LocaleMiddleware` — po `SessionMiddleware`, przed `CommonMiddleware`.
- **URL config:** `path("i18n/", include("django.conf.urls.i18n"))` — endpoint do `set_language`.
- **Tłumaczenia w kodzie:**
  - Wszystkie `verbose_name`, `help_text`, `choices` labels, etykiety formularzy → `gettext_lazy as _`.
  - W szablonach: `{% load i18n %}`, `{% trans "..." %}`, `{% blocktrans %}...{% endblocktrans %}`.
  - W widokach (komunikaty messages): `gettext as _`.
- **Pliki tłumaczeń:**
  - `locale/pl/LC_MESSAGES/django.po` (i `.mo` po kompilacji)
  - `locale/en/LC_MESSAGES/django.po`
  - Generowanie: `python manage.py makemessages -l en -l pl --ignore=venv`
  - Kompilacja: `python manage.py compilemessages`
- **Przełącznik języka w navbarze:** formularz POST do `{% url 'set_language' %}` z hidden `next` i selectem `language`. Wybór persystowany w sesji/cookie.
- **Język domyślny:** polski. Angielski dostępny przez przełącznik.
- **URLe pozostają w angielskim** (`/movies/`, `/screenings/`, `/my-bookings/`) — nie są tłumaczone (`i18n_patterns` nie używane), tłumaczeniu podlega wyłącznie zawartość.
- **Daty i waluta:** formatowane przez `{% load l10n %}` / `{{ value|localize }}` zgodnie z aktywnym językiem.

---

## 5. Logika biznesowa

### 5.1 Sprawdzanie dostępności miejsc
Metoda `Screening.available_seats_count()` używana w formularzu i widokach listujących. Liczy jako zajęte:
- Wszystkie bookingi `CONFIRMED`.
- Bookingi `PENDING` z `expires_at > now()` (czekające na płatność — miejsca są zarezerwowane).

Po `expires_at` PENDING przestaje liczyć się do zajętych — komenda `expire_pending_bookings` (FR-23) finalnie zmienia ich status na `CANCELLED`.

### 5.2 Race condition przy rezerwacji
Tworzenie `Booking` w `transaction.atomic()` z `Screening.objects.select_for_update().get(pk=...)` — blokada wiersza screeningu do końca transakcji.

### 5.3 Reguły czasowe
- Rezerwacja niedozwolona dla `start_time <= now()`.
- Anulowanie dozwolone do 1h przed seansem.
- Wszystko w `Europe/Warsaw`, `USE_TZ=True`.

### 5.4 Cena
`Booking.total_price = seats_count * screening.price` — property, nie zapisywana (single source of truth = `Screening.price`).

---

## 6. Wymagania UI/UX

- **CSS:** Bootstrap 5 lub Tailwind — spójny design system.
- **Responsywność:** 360px–1920px.
- **Navbar:** logo „KinoMania" → `/`, linki Movies / Screenings / My Bookings (jeśli zalogowany), Login / Register / Logout, **przełącznik języka PL/EN**.
- **Footer:** stopka z rokiem.
- **Dostępność:** semantyczny HTML, `alt` dla obrazów, kontrast WCAG AA.
- **Placeholder dla brakujących obrazów:** `static/img/placeholder.png`.
- **Flash messages:** górna część strony, auto-dismiss.

---

## 7. Wymagania niefunkcjonalne

| Kategoria | Wymaganie |
|---|---|
| **Wydajność** | Lista repertuaru <1s przy 200 filmach (`prefetch_related` na M2M). |
| **Bezpieczeństwo (web)** | CSRF on; hasła PBKDF2; brak `DEBUG=True` na produkcji; `seed_db` zablokowane w produkcji bez `--force`. |
| **Bezpieczeństwo (API)** | JWT (access 15 min, refresh 7 dni); throttling DRF: `anon` 100/h, `user` 1000/h, `auth` (login/register) 20/h; permissions per ViewSet (`IsAuthenticatedOrReadOnly`, `IsAdminUser`, `IsBookingOwnerOrStaff`). |
| **Stripe** | Webhook endpoint CSRF-exempt z weryfikacją sygnatury (`STRIPE_WEBHOOK_SECRET`); klucze Stripe wyłącznie w `.env` (`sk_test_…`, `whsec_…`); całość projektu na sandbox keys; idempotency keys per Booking; `client_reference_id` zawsze ustawiony. |
| **Walidacja** | Walidacja serwerowa wszędzie (forms, serializers, model `clean()`); ImageField — max 5MB, format JPG/PNG/WebP. |
| **Testy** | Patrz FR-14 — modele, widoki, formularze, race condition, webhook signature/idempotency, refund, expire command, API endpoints + throttling. Coverage threshold 80%. |
| **Code quality** | `ruff check`, `ruff format --check`, `mypy` muszą przechodzić w CI; `pre-commit` instalowane lokalnie. |
| **Konfiguracja** | Sekrety w `.env` (`django-environ`); `.env.example` w repo (z prefiksami `sk_test_…`, `whsec_…` jako wzorzec); osobne settings: `base.py` / `dev.py` / `prod.py`. |
| **i18n** | Wszystkie user-facing stringi tłumaczone (PL/EN); brak hard-coded polskiego/angielskiego w szablonach poza `{% trans %}`. API responses pozostają w angielskim (kody błędów); `Accept-Language` nie wpływa na payloady DRF. |
| **Konwencje kodu** | Identyfikatory wyłącznie po angielsku; PEP 8 (ruff format); type hints w nowych funkcjach. |
| **Commits** | Conventional Commits z scope FR (`feat(FR-07): …`); patrz `.Claude/commit_convention.md`. |

---

## 8. Struktura projektu

```
kinomania/
├── manage.py
├── pyproject.toml                # Poetry + ruff + mypy + pytest config (FR niefunkcjonalne)
├── poetry.lock
├── docker-compose.yml            # PostgreSQL 16 dla dev/prod (FR niefunkcjonalne)
├── .pre-commit-config.yaml       # ruff + mypy + pytest hooks
├── .env.example
├── .gitignore
├── README.md
├── .github/
│   ├── workflows/
│   │   └── ci.yml                # lint + mypy + pytest + coverage 80% (FR niefunkcjonalne)
│   └── pull_request_template.md
├── settings/                     # konfiguracja projektu (split base/dev/prod)
│   ├── __init__.py
│   ├── base.py
│   ├── dev.py
│   ├── prod.py
│   ├── urls.py                   # main urlconf — include API + web + webhooks
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                     # aplikacja autoryzacji
│   ├── models.py                 # custom User + UserManager
│   ├── managers.py
│   ├── forms.py                  # EmailAuthenticationForm, RegistrationForm
│   ├── views.py                  # Register, custom Login (web)
│   ├── urls.py
│   ├── admin.py                  # custom UserAdmin
│   ├── factories.py              # UserFactory (factory_boy)
│   ├── api/                      # FR-16
│   │   ├── __init__.py
│   │   ├── serializers.py        # RegisterSerializer, MeSerializer
│   │   ├── views.py              # RegisterView, MeView (token endpoints z simplejwt)
│   │   ├── urls.py
│   │   └── permissions.py
│   ├── tests/
│   │   ├── test_models.py
│   │   ├── test_views.py
│   │   └── test_api_auth.py
│   └── templates/accounts/
│       ├── login.html
│       └── register.html
├── cinema/                       # główna aplikacja
│   ├── models.py                 # Genre, Actor, Director, Hall, Movie, Screening, Booking
│   ├── views.py
│   ├── forms.py                  # BookingForm, filters
│   ├── urls.py
│   ├── admin.py
│   ├── managers.py               # custom QuerySetów (np. MovieQuerySet.upcoming)
│   ├── factories.py              # MovieFactory, ScreeningFactory, BookingFactory + warianty
│   ├── services/                 # logika biznesowa wspólna dla web i API
│   │   ├── __init__.py
│   │   └── bookings.py           # create_booking_pending, cancel_booking
│   ├── api/                      # FR-17, FR-18, FR-19
│   │   ├── __init__.py
│   │   ├── serializers.py
│   │   ├── viewsets.py           # MovieViewSet, ScreeningViewSet, BookingViewSet, AdminViewSets
│   │   ├── permissions.py        # IsBookingOwnerOrStaff
│   │   ├── filters.py            # FilterSets (django-filter)
│   │   └── urls.py
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── seed_db.py        # FR-13
│   ├── tests/
│   │   ├── test_models.py
│   │   ├── test_views.py
│   │   ├── test_forms.py
│   │   ├── test_business_logic.py
│   │   ├── test_api_movies.py
│   │   ├── test_api_screenings.py
│   │   └── test_api_bookings.py
│   └── templates/cinema/
│       ├── base.html             # navbar z language switcher
│       ├── movie_list.html
│       ├── movie_detail.html
│       ├── screening_list.html
│       ├── booking_form.html
│       ├── booking_detail.html
│       └── my_bookings.html
├── payments/                     # NEW — FR-21..FR-24
│   ├── __init__.py
│   ├── models.py                 # StripeEvent (3.9)
│   ├── views.py                  # StripeWebhookView, CheckoutView (web)
│   ├── urls.py                   # /webhooks/stripe/, /bookings/<id>/checkout/
│   ├── admin.py                  # StripeEventAdmin (read-only)
│   ├── factories.py              # StripeEventFactory
│   ├── services/
│   │   ├── __init__.py
│   │   └── stripe.py             # create_checkout_session, refund, construct_event
│   ├── api/                      # FR-21 (API), FR-22 (webhook unified — opcjonalnie pod /api/)
│   │   ├── __init__.py
│   │   ├── serializers.py
│   │   ├── views.py              # CheckoutAPIView
│   │   └── urls.py
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── expire_pending_bookings.py   # FR-23
│   └── tests/
│       ├── test_webhook.py
│       ├── test_expire_command.py
│       └── test_refund.py
├── locale/                       # tłumaczenia FR-15
│   ├── pl/LC_MESSAGES/
│   │   ├── django.po
│   │   └── django.mo
│   └── en/LC_MESSAGES/
│       ├── django.po
│       └── django.mo
├── static/
│   ├── css/
│   ├── js/
│   └── img/
├── media/                        # uploads (gitignore)
│   ├── posters/
│   ├── actors/
│   └── directors/
├── conftest.py                   # globalne fixtures pytest (Stripe mocks, etc.)
└── docs/                         # dokumentacja procesu (specs, plans, retros)
    ├── superpowers/
    │   ├── specs/
    │   └── plans/
    └── retros/
```

---

## 9. Plan implementacji

Ten dokument opisuje **wymagania funkcjonalne** (co system ma robić). Plan implementacji (User Stories, kolejność, milestones, branche, commity) znajduje się w osobnych dokumentach:

- **`.Claude/backlog.md`** — Product backlog z 43 User Stories rozłożonymi na 5 milestone'ów (M1 Foundation → M5 Polish), każdy zakończony tagiem release (`v0.1.0` → `v1.0.0`).
- **`.Claude/workflow_scrum_agile.md`** — proces SCRUM/AGILE: model Hybrid Kanban + monthly milestones, role, DoR, DoD, ceremonie, eskalacja.
- **`.Claude/tooling_stack.md`** — kanoniczne konfiguracje narzędzi (Poetry, ruff, mypy, pytest, pre-commit, GitHub Actions, Docker Compose, Stripe CLI).
- **`.Claude/commit_convention.md`** — Conventional Commits z scope FR (`feat(FR-07): …`), strategia branchy (`feat/FR-XX-slug`, `release/MX`), PR template, release flow per milestone.

> **Kolejność krytyczna (niezmienna):** Custom `User` model + `accounts.User` w `AUTH_USER_MODEL` muszą być utworzone **przed pierwszą migracją** każdego modelu odwołującego się do `settings.AUTH_USER_MODEL`. Zmiana `AUTH_USER_MODEL` po pierwszej migracji wymaga resetu bazy. Patrz US-06 w `backlog.md`.

---

## 10. Kryteria odbioru projektu (Definition of Done)

- [ ] Wszystkie wymagania FR-01 do FR-24 zaimplementowane i ręcznie przetestowane.
- [ ] **Identyfikatory w kodzie wyłącznie po angielsku** (modele, pola, klasy, funkcje, zmienne, URLe).
- [ ] **Custom User model** używa `email` jako `USERNAME_FIELD`; **brak pola username**.
- [ ] Logowanie działa poprzez email + hasło; rejestracja przyjmuje email (nie username).
- [ ] Migracje działają na czystej bazie (`migrate` od zera).
- [ ] `poetry run python manage.py seed_db` wypełnia bazę realistycznymi danymi (FR-13), w tym 5% PENDING dla testowania expiration.
- [ ] `poetry run pytest --cov-fail-under=80` przechodzi bez błędów (FR-14); coverage globalny ≥ 80%.
- [ ] `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .` — bez błędów.
- [ ] CI (GitHub Actions) zielone na `main` na ostatnim commicie milestone'a.
- [ ] Aplikacja uruchamia się lokalnie (`runserver`) bez ostrzeżeń.
- [ ] Panel admin (FR-11): `search_fields`, `list_filter`, `inlines`, custom `list_display` — dla każdego modelu, z dostosowanym `UserAdmin` dla custom User.
- [ ] Niezalogowany user nie ma dostępu do rezerwacji ani panelu „my bookings".
- [ ] Rezerwacja respektuje limit miejsc (test edge case: ostatnie miejsce, race condition).
- [ ] Zwiastun YouTube poprawnie się osadza.
- [ ] **Przełącznik języka PL/EN działa** — zmiana języka aktualizuje wszystkie etykiety, komunikaty, przyciski.
- [ ] Pliki `locale/pl/LC_MESSAGES/django.po` i `locale/en/LC_MESSAGES/django.po` wypełnione, `.mo` skompilowane.
- [ ] Brak hard-coded sekretów; `.env.example` w repo (z prefiksami Stripe `sk_test_…`, `whsec_…`).
- [ ] README opisuje pełny setup w tym `makemessages` / `compilemessages` oraz `stripe listen` (Stripe CLI).
- [ ] `pyproject.toml` (Poetry) zawiera wszystkie deps z FR-1.2; `poetry install` na czystej maszynie wystarcza do uruchomienia projektu.
- [ ] **Stripe Checkout flow** działa end-to-end na sandbox keys (PENDING → Checkout → CONFIRMED przez webhook).
- [ ] **Webhook idempotency** potwierdzona testem (`test_webhook_idempotent_on_duplicate_event`).
- [ ] **`/api/v1/docs/`** zwraca poprawną Swagger UI z opisami i przykładami; **`/api/v1/schema/`** zwraca poprawny OpenAPI 3.1.
- [ ] **JWT** access/refresh działa (login → token → refresh → me); throttling skonfigurowany dla `anon`/`user`/`auth`.
- [ ] **Refund flow** działa — anulowanie `CONFIRMED` bookingu wywołuje Stripe Refund (mocked w testach, real w manualnym smoke teście na sandboxie).
- [ ] **`expire_pending_bookings`** poprawnie cancelluje przedawnione PENDING (test + manualne wywołanie).
