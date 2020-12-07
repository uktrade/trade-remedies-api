import json

from django.core.management.base import BaseCommand, CommandError

from cases.models.submissiondocument import SubmissionDocumentType

from core.models import JobTitle

from organisations.models import Organisation

from workflow.models import WorkflowTemplate


LEGACY_INITALISM = "TRID"
INITALISM = "TRA"
LEGACY_ORGANISATION_NAME = "Trade Remedies Investigations Directorate"
ORGANISATION_NAME = "Trade Remedies Authority"


def convert(from_initialism, to_initialism):
    # cases.submissiondocumenttype
    tra_document = SubmissionDocumentType.object.filter(
        name=f"{from_initialism} Document"
    ).first()

    tra_document.name = f"{to_initialism} Document"
    tra_document.save()

    # workflow_template_anti_dumping.json
    # workflow_template_anti_subsidy.json
    # workflow_template_safeguards.json
    # workflow_template_trans_anti_dumping.json
    # workflow_template_trans_anti_subsidy.json 
    # workflow_template_trans_safeguards.json
    workflows = [
        "Anti-dumping Review",
        "Anti-subsidy investigation",
        "Safeguarding",
        "Transitional Anti-dumping Review",
        "Transitional Anti-subsidy Review",
        "Transition safeguarding review",
    ]

    for workflow_name in workflows:
        workflow = WorkflowTemplate.objects.filter(
            name=workflow_name
        ).first()

        updated_json_txt = json.dumps(
            workflow.template
        ).replace(
            f"{from_initialism} approval of the decision",
            f"{to_initialism} approval of the decision",
        )
        workflow.template = json.loads(updated_json_txt)
        workflow.save()

    # job_titles.json
    job_title = JobTitle.objects.filter(
        name=f"{from_initialism} Other",
    )

    job_title.name = f"{to_initialism} Other"
    job_title.save()

    # tra_organisations.json 
    organisation = Organisation.objects.filter(
        name=from_name,
    )

    organisation.name = to_name
    organisation.save()


def update_brand():
    convert(
        LEGACY_INITALISM,
        INITALISM,
        LEGACY_ORGANISATION_NAME,
        ORGANISATION_NAME,
    )


def revert_brand():
    convert(
        INITALISM,
        LEGACY_INITALISM,
        ORGANISATION_NAME,
        LEGACY_ORGANISATION_NAME,
    )


class Command(BaseCommand):
    help = (
        "Update system branding."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--revert",
            action="revert",
            help='Reverts brand to old version',
        )

    def handle(self, *args, **options):
        if options["revert"]:
            revert_brand()
            return

        update_brand()
        return
