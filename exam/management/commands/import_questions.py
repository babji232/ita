from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from exam.importer import import_csv


class Command(BaseCommand):
    help = "Import questions from a CSV file (default: data/questions.csv)"

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default=str(Path(settings.BASE_DIR) / "data" / "questions.csv"))

    def handle(self, *args, **opts):
        with open(opts["path"], "rb") as f:
            created, skipped, errors = import_csv(f)
        self.stdout.write(self.style.SUCCESS(f"Created {created}, skipped duplicates {skipped}"))
        for e in errors[:20]:
            self.stdout.write(self.style.WARNING(e))
