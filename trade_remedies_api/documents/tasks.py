from celery import shared_task
from celery.utils.log import get_task_logger
from documents.constants import INDEX_STATE_NOT_INDEXED
from django.conf import settings

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=4)
def checksum_document(self, document_id):
    from documents.models import Document

    logger.info(f"Prepare document task for: '{document_id}'")
    try:
        doc = Document.objects.get(id=document_id)
        doc.set_md5_checksum()
    except Document.DoesNotExist:
        logger.warning(
            f"Failed to prepare document: '{document_id}' does" " not exist (will retry)"
        )
        raise self.retry(countdown=10)
    except Exception as e:
        logger.warning(f"Failed to prepare document '{document_id}': {e}" " (will retry)")
        raise self.retry(countdown=10)


@shared_task(bind=True, max_retries=3)
def index_document(self, document_id, case_id=None):
    from documents.models import Document

    logger.info(f"Index document task for: '{document_id}'")
    try:
        document = Document.objects.get(id=document_id)
        result = document.open_search_index(case=case_id)
        logger.info(result)
    except Document.DoesNotExist:
        logger.warning(f"Failed to index document: '{document_id}' does" f" not exist (will retry)")
        raise self.retry(countdown=10)
    except Exception as e:
        logger.warning(f"Failed to index document '{document_id}': {e}" " (will retry)")
        raise self.retry(countdown=10)


@shared_task()
def index_documents(force=False):
    from documents.models import Document

    logger.info("Starting periodic document indexing")
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
