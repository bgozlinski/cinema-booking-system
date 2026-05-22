import random
import uuid
from datetime import timedelta
from decimal import Decimal
from math import floor

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
from apps.payments.models import StripeEvent

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

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with test data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow seeding when DEBUG=False (dev only).",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="Number of users to seed (default 10).",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete non-superuser users before seeding.",
        )
        parser.add_argument(
            "--append",
            action="store_true",
            help="Create only missing seed users (skip existing by email).",
        )
        parser.add_argument(
            "--movies",
            type=int,
            default=20,
            help="Number of movies to seed (default 20).",
        )
        parser.add_argument(
            "--screenings",
            type=int,
            default=100,
            help="Number of screenings to seed (default 100).",
        )
        parser.add_argument(
            "--bookings",
            type=int,
            default=30,
            help="Number of bookings to seed (default 30).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_db is disabled when DEBUG=False. Use --force to override (DEV ONLY)."
            )
        if not settings.DEBUG and options["force"]:
            self.stderr.write(
                self.style.WARNING(
                    "WARNING: Running seed_db in non-DEBUG environment. This is intended for dev only."
                )
            )
        if options["append"] and options["flush"]:
            raise CommandError("--flush and --append are mutually exclusive")

        n = options["users"]
        if n < 1:
            raise CommandError("--users must be >= 1")

        active_count = floor(n * 0.8)
        inactive_count = n - active_count
        fake = Faker("pl_PL")
        password = settings.SEED_DB_DEFAULT_PASSWORD

        non_super_count = User.objects.filter(is_superuser=False).count()
        cinema_count = (
            Genre.objects.count()
            + Hall.objects.count()
            + Actor.objects.count()
            + Director.objects.count()
            + Movie.objects.count()
            + Screening.objects.count()
            + Booking.objects.count()
            + StripeEvent.objects.count()
        )

        if options["flush"] or options["append"]:
            pass
        elif non_super_count > 0 or cinema_count > 0:
            raise CommandError(
                f"Database not empty (found {non_super_count} non-superuser user(s), "
                f"{cinema_count} cinema row(s)). Use --flush to wipe or --append to add."
            )

        created_count = 0
        skipped_count = 0
        with transaction.atomic():
            if options["flush"]:
                StripeEvent.objects.all().delete()
                Booking.objects.all().delete()
                Screening.objects.all().delete()
                Movie.objects.all().delete()
                Hall.objects.all().delete()
                Actor.objects.all().delete()
                Director.objects.all().delete()
                Genre.objects.all().delete()
                User.objects.filter(is_superuser=False).delete()
            self._seed_genres()
            halls = self._seed_halls()
            actors = self._seed_actors(fake)
            directors = self._seed_directors(fake)
            genre_list = list(Genre.objects.all())
            movies = self._seed_movies(fake, options["movies"], genre_list, actors, directors)
            self._seed_screenings(options["screenings"], movies, halls)

            for i in range(1, n + 1):
                email = f"seed.user{i}@kinomania.local"
                if options["append"] and User.objects.filter(email=email).exists():
                    self.stdout.write(f"Skipping existing: {email}")
                    skipped_count += 1
                    continue
                user = User(
                    email=email,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    is_active=(i <= active_count),
                    is_staff=False,
                    is_superuser=False,
                )
                user.set_password(password)
                user.save()
                created_count += 1

            # Bookings + StripeEvents (US-18 / FR-3.8 + FR-3.9)
            if options["bookings"] > 0:
                seed_users = list(User.objects.filter(is_superuser=False))
                seed_screenings = list(Screening.objects.all())
                if seed_users and seed_screenings:
                    confirmed_bookings = self._seed_bookings(
                        options["bookings"], seed_screenings, seed_users
                    )
                    self._seed_stripe_events(confirmed_bookings)

        if options["append"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Appended {created_count} users ({skipped_count} skipped). "
                    f"Default password: {password}."
                )
            )
        else:
            inactive_emails = [
                f"seed.user{i}@kinomania.local" for i in range(active_count + 1, n + 1)
            ]
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {Genre.objects.count()} genres, "
                    f"{Hall.objects.count()} halls, "
                    f"{Actor.objects.count()} actors, "
                    f"{Director.objects.count()} directors, "
                    f"{Movie.objects.count()} movies, "
                    f"{Screening.objects.count()} screenings, "
                    f"{Booking.objects.count()} bookings, "
                    f"{StripeEvent.objects.count()} stripe events, "
                    f"and {created_count} users ({active_count} active, "
                    f"{inactive_count} inactive). Default password: {password}."
                )
            )

            if inactive_emails:
                self.stdout.write("Inactive accounts:")
                for email in inactive_emails:
                    self.stdout.write(f"  {email}")

    def _seed_genres(self):
        created = 0
        for name in GENRE_NAMES:
            _, was_created = Genre.objects.get_or_create(name=name)
            if was_created:
                created += 1
        return created

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

    def _seed_screenings(self, n, movies, halls):
        now = timezone.now()
        for _ in range(n):
            Screening.objects.create(
                movie=random.choice(movies),
                hall=random.choice(halls),
                start_time=now
                + timedelta(
                    days=random.randint(-7, 30),
                    hours=random.randint(0, 23),
                ),
                price=Decimal(f"{random.uniform(25, 55):.2f}"),
            )

    def _seed_bookings(self, count, screenings, users):
        """Generate bookings with status distribution ~85% CONFIRMED / ~5% PENDING /
        ~10% CANCELLED. Guarantees >=1 of each status when count >= 3 — gives dev DB
        deterministic coverage of all states for manual testing. Returns list of
        CONFIRMED bookings for _seed_stripe_events."""
        guaranteed = (
            [BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED]
            if count >= 3
            else []
        )
        remaining = count - len(guaranteed)
        statuses = guaranteed + random.choices(
            [BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED],
            weights=[85, 5, 10],
            k=remaining,
        )
        random.shuffle(statuses)
        confirmed = []
        for status in statuses:
            user = random.choice(users)
            screening = random.choice(screenings)
            seats = random.randint(1, 10)

            booking_kwargs = {
                "user": user,
                "screening": screening,
                "seats_count": seats,
                "status": status,
            }
            if status == BookingStatus.PENDING:
                # 50/50 past/future expires_at — for testing expire_pending_bookings (US-26)
                offset = random.choice([-1, 1]) * timedelta(minutes=random.randint(5, 60))
                booking_kwargs["expires_at"] = timezone.now() + offset
            elif status == BookingStatus.CONFIRMED:
                booking_kwargs["stripe_session_id"] = f"cs_seed_{uuid.uuid4().hex[:16]}"
                booking_kwargs["stripe_payment_intent_id"] = f"pi_seed_{uuid.uuid4().hex[:16]}"

            booking = Booking.objects.create(**booking_kwargs)
            if status == BookingStatus.CONFIRMED:
                confirmed.append(booking)
        return confirmed

    def _seed_stripe_events(self, confirmed_bookings):
        """One StripeEvent per CONFIRMED booking — checkout.session.completed event
        with payload referencing booking via client_reference_id."""
        for booking in confirmed_bookings:
            event_id = f"evt_seed_{uuid.uuid4().hex[:16]}"
            StripeEvent.objects.create(
                event_id=event_id,
                event_type="checkout.session.completed",
                payload={
                    "id": event_id,
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": booking.stripe_session_id,
                            "client_reference_id": str(booking.id),
                            "payment_intent": booking.stripe_payment_intent_id,
                        }
                    },
                },
                processed_at=timezone.now(),
            )
