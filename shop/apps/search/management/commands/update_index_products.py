"""
Management command: update_index_products

Full reindex of all browsable products into Manticore.
"""

import time
import logging
from django.core.management.base import BaseCommand
from shop.apps.search.indexer import ProductManticoreIndex, _chunked
from shop.apps.search import defaults

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild the Manticore products search index."

    def add_arguments(self, parser):
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=defaults.INDEXING_CHUNK_SIZE,
            help="Number of documents per bulk insert.",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Print per-chunk timing information.",
        )

    def handle(self, *args, **options):
        chunk_size = options["chunk_size"]
        debug = options["debug"]

        self.stdout.write("Indexing products...")
        index = ProductManticoreIndex()
        qs = index.get_queryset()

        # Drop + recreate table so schema is always current
        index.ensure_schema(drop=True)

        total = 0
        chunk_num = 0
        for chunk in _chunked(qs.iterator(chunk_size=chunk_size), chunk_size):
            chunk_num += 1
            t0 = time.time()
            pairs = []
            for obj in chunk:
                try:
                    doc = index.make_document(obj)
                    pairs.append((obj.id, doc))
                except Exception as exc:
                    self.stderr.write(
                        f"Failed to build doc for product id={obj.id}: {exc}"
                    )
            if pairs:
                index.bulk_replace(pairs)
                total += len(pairs)
            if debug:
                elapsed = time.time() - t0
                self.stdout.write(
                    f"  chunk {chunk_num}: {len(pairs)} docs in {elapsed:.2f}s"
                )

        self.stdout.write(self.style.SUCCESS(f"Indexed {total} products."))
