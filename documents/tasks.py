from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q
from documents.constants import INDEX_STATE_NOT_INDEXED

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=4)
def prepare_document(self, document_id, case_id=None):
    logger.warning(f"Prepare document for {document_id}")
    from documents.models import Document

    doc = Document.objects.get(id=document_id)
    try:
        doc.prepare_document(case=case_id)
    except Exception as exc:
        logger.error(f"Error preparing document {document_id}: {exc}.")
        raise self.retry(exc=exc, countdown=10)


@shared_task()
def prepare_pending_documents():
    from documents.models import Document

    pending_docs = Document.objects.filter(
        Q(checksum__isnull=True) | Q(safe__isnull=True)
    ).values_list("id", flat=True)
    for doc_id in pending_docs:
        prepare_document.delay(doc_id)


@shared_task()
def index_document(document_id, case_id=None):
    from documents.models import Document

    document = Document.objects.get(id=document_id)
    result = document.elastic_index(case=case_id)
    print(result)


@shared_task()
def index_documents(force=False):
    from documents.models import Document

    logger.info("Index cycle starts")
    document_ids = Document.objects.filter(deleted_at__isnull=True,)
    if not force:
        document_ids = Document.objects.filter(index_state=INDEX_STATE_NOT_INDEXED)
    document_ids = document_ids.values_list("id", flat=True)
    for document_id in document_ids:
        index_document.delay(document_id)
