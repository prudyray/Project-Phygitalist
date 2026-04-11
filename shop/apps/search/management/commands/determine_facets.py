"""
Management command: determine_facets

Introspects ProductAttributes and prints which ones would make good facets,
sorted by number of products that have them set.

Usage:
  # See attribute codes and counts:
  ./manage.py determine_facets

  # Output a starter OSCAR_SEARCH_FACETS config skeleton:
  ./manage.py determine_facets --json
"""

import json
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import models
from oscar.core.loading import get_model

ProductAttribute = get_model("catalogue", "ProductAttribute")


class Command(BaseCommand):
    help = "Inspect product attributes to suggest OSCAR_SEARCH_FACETS config."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true", help="Output facets config skeleton as JSON."
        )

    def handle(self, *args, **options):
        facets = defaultdict(int)
        facet_labels = {}
        for code, label, num_products in ProductAttribute.objects.annotate(
            num_products=models.Count("product")
        ).values_list("code", "name", "num_products"):
            facets[code] += num_products
            facet_labels[code] = label

        sorted_facets = sorted(facets.items(), key=lambda x: x[1], reverse=True)

        if options["json"]:
            self.stdout.write(
                json.dumps(
                    [
                        {
                            "name": f"attr_{code}",
                            "label": facet_labels[code],
                            "type": "term",
                        }
                        for code, _ in sorted_facets
                    ],
                    indent=4,
                )
            )
        else:
            self.stdout.write(
                "%-40s %s" % ("Attribute code", "# products")
            )
            self.stdout.write("-" * 55)
            for code, num_products in sorted_facets:
                self.stdout.write("%-40s %d" % (code, num_products))
