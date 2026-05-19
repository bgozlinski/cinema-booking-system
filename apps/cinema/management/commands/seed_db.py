from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Seed the database with test data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow seeding when DEBUG=False (dev only).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_db is disabled when DEBUG=False. Use --force to override (DEV ONLY)."
            )
        if not settings.DEBUG and options["force"]:
            self.stderr.write(
                self.style.WARNING(
                    "Running seed_db in non-DEBUG environment. This is intended for dev only."
                )
            )
