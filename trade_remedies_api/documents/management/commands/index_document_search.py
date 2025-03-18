from django.core.management.base import BaseCommand
from django.conf import settings

from documents.models import Document
from documents.constants import INDEX_STATE_NOT_INDEXED
from documents.tasks import index_document

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Index documents for open searching"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force indexing of all non-deleted documents",
        )

    def handle(self, *args, **options):
        force = options["force"]

        logger.info("Starting document indexing")
        if not force:
            # Just non-indexed documents
            document_ids = Document.objects.filter(index_state=INDEX_STATE_NOT_INDEXED)
        else:
            # All non-deleted documents
            document_ids = Document.objects.filter(
                deleted_at__isnull=True,
            )

        all_ids = document_ids.values_list("id", flat=True)

        for document_id in all_ids:
            if settings.RUN_ASYNC:
                index_document.delay(document_id)
            else:
                index_document(document_id)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully queued {len(all_ids)} documents for indexing")
        )
