"""
Management command: update_oscar_index

Orchestrates a full reindex of both products and categories.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Rebuild all Manticore search indexes (products + categories)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Print per-chunk timing information.",
        )

    def handle(self, *args, **options):
        debug = options["debug"]
        call_command("update_index_products", debug=debug, verbosity=options["verbosity"])
        call_command("update_index_categories", debug=debug, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS("All indexes rebuilt."))
