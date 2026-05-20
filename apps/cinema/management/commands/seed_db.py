import random
from math import floor

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

from apps.cinema.models import Actor, Director, Genre, Hall

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

        if options["flush"] or options["append"]:
            pass
        elif non_super_count > 0:
            raise CommandError(
                f"Database not empty (found {non_super_count} non-superuser user(s)). "
                f"Use --flush to wipe non-superusers or --append to add only missing."
            )

        created_count = 0
        skipped_count = 0
        with transaction.atomic():
            if options["flush"]:
                User.objects.filter(is_superuser=False).delete()
            self._seed_genres()
            self._seed_halls()
            self._seed_actors(fake)
            self._seed_directors(fake)
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
                    f"Seeded {created_count} users ({active_count} active, "
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
