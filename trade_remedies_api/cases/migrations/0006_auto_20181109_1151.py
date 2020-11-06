import logging

from django.db import migrations
from cases.models import SubmissionDocument, SubmissionDocumentType, Submission
from cases.constants import (
    SUBMISSION_DOCUMENT_TYPE_TRA,
    SUBMISSION_DOCUMENT_TYPE_CUSTOMER,
    SUBMISSION_DOCUMENT_TYPE_DEFICIENCY,
)

logger = logging.getLogger(__name__)


def submission_documents_type(apps, schema_editor):
    try:
        subdocs = SubmissionDocument.objects.all()
        tra, created = SubmissionDocumentType.objects.get_or_create(
            id=SUBMISSION_DOCUMENT_TYPE_TRA, name="TRA Document", key="caseworker"
        )
        cust, created = SubmissionDocumentType.objects.get_or_create(
            id=SUBMISSION_DOCUMENT_TYPE_CUSTOMER, name="Customer Document", key="respondent"
        )
        defic, created = SubmissionDocumentType.objects.get_or_create(
            id=SUBMISSION_DOCUMENT_TYPE_DEFICIENCY, name="Deficiency Document", key="deficiency"
        )
        for subdoc in subdocs:
            if subdoc.document.created_by.is_tra():
                subdoc.type = tra
            else:
                subdoc.type = cust
            subdoc._disable_audit = True
            subdoc.save()
            logger.info(f"{subdoc.type} for {subdoc}")
        subs = Submission.objects.filter(deficiency_document__isnull=False)
        for sub in subs:
            sub.add_document(sub.deficiency_document, defic)
            logger.info(f"Sub deficiency for {sub}")
    except Exception:
        pass  # New db?


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0005_auto_20181108_1750"),
    ]

    operations = [
        # migrations.RunPython(submission_documents_type)
    ]
