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


class Command(BaseCommand):
    help = (
        "Update system branding."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--revert",
            action="store_true",
            help='Reverts brand to old version',
        )

    def print_success(self, msg):
        self.stdout.write(
            self.style.SUCCESS(
                msg
            )
        )

    def convert(self, from_initialism, to_initialism, from_org_name, to_org_name):
        # cases.submissiondocumenttype
        tra_document = SubmissionDocumentType.objects.filter(
            name=f"{from_initialism} Document"
        ).first()

        tra_document.name = f"{to_initialism} Document"
        tra_document.save()

        self.print_success(f"Updated {tra_document}")

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

            self.print_success(f"Updated {workflow}")

        # job_titles.json
        job_title = JobTitle.objects.filter(
            name=f"{from_initialism} Other",
        ).first()

        job_title.name = f"{to_initialism} Other"
        job_title.save()

        self.print_success(f"Updated {job_title}")

        # tra_organisations.json 
        organisation = Organisation.objects.filter(
            name=from_org_name,
        ).first()

        organisation.name = to_org_name
        organisation.save()

        self.print_success(f"Updated {organisation}")

    def update_brand(self):
        self.convert(
            LEGACY_INITALISM,
            INITALISM,
            LEGACY_ORGANISATION_NAME,
            ORGANISATION_NAME,
        )


    def revert_brand(self):
        self.convert(
            INITALISM,
            LEGACY_INITALISM,
            ORGANISATION_NAME,
            LEGACY_ORGANISATION_NAME,
        )

    def handle(self, *args, **options):
        if options["revert"]:
            self.revert_brand()
            return

        self.update_brand()
        return
