import colorsys
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
from django.utils.text import slugify
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

# Curated, presentable demo movies (original fictional titles + synopses) used for the
# README screenshots (US-43). Real movie titles/posters are intentionally avoided so the
# repo stays license-clean; posters are generated as original gradient art via --posters.
# Pool >= the default --movies=20 so a plain run uses these; counts beyond the pool fall
# back to faker. Durations stay within the 80..180 range the seed tests assert.
CURATED_MOVIES = (
    (
        "Echoes of Tomorrow",
        128,
        "A burnt-out physicist discovers her late mentor's machine can replay any moment of the past — but each rerun quietly rewrites her present.",
    ),
    (
        "The Last Lighthouse",
        112,
        "On a storm-battered island, an ageing keeper and a runaway teenager strike an uneasy friendship across the longest winter of their lives.",
    ),
    (
        "Midnight in Kraków",
        99,
        "Two strangers miss the last tram home and spend a single restless night wandering the old town, daring each other to be honest.",
    ),
    (
        "Crimson Harvest",
        104,
        "When the wheat turns red overnight, a remote farming village learns that the land remembers every debt — and intends to collect.",
    ),
    (
        "Paper Aeroplanes",
        96,
        "A nine-year-old convinced his absent father is an astronaut builds a fleet of paper planes to send him letters from the rooftop.",
    ),
    (
        "Quantum Drift",
        141,
        "A salvage crew chasing a derelict freighter through a collapsing wormhole find their own future selves waiting on board.",
    ),
    (
        "The Silent Orchestra",
        118,
        "A deaf conductor stakes everything on one final concert, teaching a fractured ensemble to feel the music they can no longer agree on.",
    ),
    (
        "Neon Wolves",
        107,
        "In a rain-soaked megacity, a courier with a stolen memory chip outruns three rival syndicates and her own erased past.",
    ),
    (
        "A Letter to the Sea",
        109,
        "Each summer a widow throws a bottled letter into the tide; the summer one washes back answered, she sets out to find the reader.",
    ),
    (
        "Glasshouse",
        101,
        "Four colleagues trapped overnight in a smart office tower realise the building's AI has decided only one of them should leave.",
    ),
    (
        "The Cartographer's Daughter",
        133,
        "Inheriting her father's unfinished map, a young woman follows its blank spaces into a valley that refuses to be measured.",
    ),
    (
        "Static",
        89,
        "A late-night radio host starts receiving call-ins from listeners who haven't tuned in yet — and one of them knows how she dies.",
    ),
    (
        "Borrowed Time",
        116,
        "A small-town accountant given six months to live spends his savings undoing every quiet wrong he ever let slide.",
    ),
    (
        "Sunflower County",
        94,
        "A failing roadside diner becomes the unlikely stage for a town's last summer before the highway bypass erases it from the map.",
    ),
    (
        "The Ninth Door",
        121,
        "Restoring an abandoned theatre, a stagehand finds a dressing room that was bricked up for a reason no one will name.",
    ),
    (
        "Cold Harbor",
        138,
        "Two brothers on opposite sides of a forgotten border war meet for one night in the no-man's-land between their trenches.",
    ),
    (
        "Tangerine Skies",
        92,
        "A grounded pilot and a stubborn orchard owner spend a chaotic harvest season learning that crash landings come in many forms.",
    ),
    (
        "The Hollow King",
        147,
        "A reluctant heir must wear a crown that slowly hollows out whoever rules, while the kingdom waits to see what is left of him.",
    ),
    (
        "Frostbite Avenue",
        97,
        "When the snow won't stop falling on one ordinary street, the neighbours discover the storm is keeping something out — or in.",
    ),
    (
        "Saturn Ascending",
        152,
        "The first colonists of a ringed moon vote on whether to wake the rest of humanity, knowing the answer will outlive them all.",
    ),
    (
        "Origami Heart",
        88,
        "A reclusive paper artist folds a new figure for every regret, until a curious courier starts unfolding them one by one.",
    ),
    (
        "Driftwood",
        113,
        "Three estranged siblings sail their father's leaking boat to scatter his ashes, with only a hand-drawn chart and old grudges aboard.",
    ),
    (
        "Comet Season",
        95,
        "Every eleven years a comet grants the town one wish; this year two rival astronomers fall for each other while trying to claim it.",
    ),
    (
        "The Understudy",
        124,
        "A perennial second-choice actress finally gets the lead — on the night she realises the role may be rewriting who she is offstage.",
    ),
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
        parser.add_argument(
            "--posters",
            action="store_true",
            help="Generate placeholder poster images for movies (Pillow). "
            "Off by default to keep the test suite fast and avoid writing to MEDIA_ROOT.",
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
            movies = self._seed_movies(
                fake, options["movies"], genre_list, actors, directors, options["posters"]
            )
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

    def _seed_movies(self, fake, n, genres, actors, directors, with_posters=False):
        movies = []
        today = timezone.now().date()
        for i in range(n):
            if i < len(CURATED_MOVIES):
                title, duration, description = CURATED_MOVIES[i]
            else:
                title = fake.catch_phrase()
                duration = random.randint(80, 180)
                description = fake.paragraph(nb_sentences=5)
            movie = Movie.objects.create(
                title=title,
                description=description,
                release_date=today - timedelta(days=random.randint(0, 730)),
                duration_minutes=duration,
            )
            movie.genres.set(random.sample(genres, k=random.randint(1, 3)))
            movie.actors.set(random.sample(actors, k=random.randint(3, 8)))
            movie.directors.set(random.sample(directors, k=random.randint(1, 2)))
            if with_posters:
                self._attach_poster(movie)
            movies.append(movie)
        return movies

    def _attach_poster(self, movie):
        """Generate an original gradient placeholder poster (Pillow) and attach it to the
        movie. Only invoked when --posters is passed, so the default seed (and the test
        suite) writes no image files. The art is generated, not bundled, so the repo never
        ships copyrighted poster images."""
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image, ImageDraw, ImageFont

        width, height = 400, 600
        # Stable-ish accent hue derived from the title so posters look varied.
        hue = (hash(movie.title) % 360) / 360.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.45)
        top = (int(r * 255), int(g * 255), int(b * 255))
        bottom = (12, 12, 18)  # near-black — matches the dark UI theme

        img = Image.new("RGB", (width, height), bottom)
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / height
            draw.line(
                [(0, y), (width, y)],
                fill=tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)),
            )

        title_font = ImageFont.load_default(size=34)
        footer_font = ImageFont.load_default(size=18)

        # Word-wrap the title to the poster width.
        margin = 32
        max_text_width = width - 2 * margin
        lines: list[str] = []
        current = ""
        for word in movie.title.split():
            candidate = f"{current} {word}".strip()
            if not current or draw.textlength(candidate, font=title_font) <= max_text_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)

        line_height = 44
        y = (height - line_height * len(lines)) // 2
        for line in lines:
            line_width = draw.textlength(line, font=title_font)
            draw.text(((width - line_width) / 2, y), line, font=title_font, fill=(245, 245, 250))
            y += line_height

        footer = "KINOMANIA"
        footer_width = draw.textlength(footer, font=footer_font)
        draw.text(
            ((width - footer_width) / 2, height - 56),
            footer,
            font=footer_font,
            fill=(170, 170, 185),
        )

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        movie.poster.save(f"{slugify(movie.title)}.png", ContentFile(buffer.getvalue()), save=True)

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
