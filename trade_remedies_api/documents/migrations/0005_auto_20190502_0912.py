import logging

from django.db import migrations
from documents.models import DocumentBundle

logger = logging.getLogger(__name__)


def migrate_case_documents(apps, schema_editor):
    try:
        from cases.models import CaseDocument, SubmissionType
        from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST

        case_documents = CaseDocument.objects.all()
        reg_interest = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        case_index = {}
        logger.info("Indexing old case documents")
        for case_doc in case_documents:
            case_id = str(case_doc.case.id)
            case_index.setdefault(
                case_id,
                {
                    "case": case_doc.case,
                    "created_by": case_doc.created_by,
                    "created_at": case_doc.created_at,
                    "documents": [],
                },
            )
            case_index[case_id]["documents"].append(case_doc.document)
        logger.info(f"Indexed {len(case_index)} cases")
        for _, params in case_index.items():
            bundle, created = DocumentBundle.objects.get_or_create(
                case=params["case"], submission_type=reg_interest
            )
            bundle.status = "LIVE"
            bundle.created_by = params["created_by"]
            bundle.created_at = params["created_at"]
            bundle.finalised_by = params["created_by"]
            bundle.finalised_at = params["created_at"]
            bundle.save()
            logger.info(f"Bundle created for {bundle.case} (created ?= {created})")
            bundle.documents.clear()
            logger.info(f"Adding {len(params['documents'])} documents to bundle")
            for doc in params["documents"]:
                bundle.documents.add(doc)
    except Exception as exc:
        logger.error(f"Failed. Are we in test? If so that's ok... (reason in exception)", exc_info=True)


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0004_auto_20190424_1409"),
    ]

    operations = [
        # migrations.RunPython(migrate_case_documents)
    ]
