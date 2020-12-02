from django.core.management.base import BaseCommand, CommandError
from organisations.models import Organisation
from cases.models import SubmissionDocumentType
from cases.models import CaseStage
from core.models import JobTitle
# from workflow.models import WorkflowTemplate


class Command(BaseCommand):
    help = "Update the name of the Trade Authority organisation."

    def add_arguments(self, parser):
        pass
        # parser.add_argument("old_name", type=str, help="old name of organisation")
        # parser.add_argument("new_name", type=str, help="new name of organisation")

    def handle(self, *args, **options):

        try:
            trade_authority_organisation = Organisation.objects.get(name="Trade Remedies Investigations Directorate")
        except Organisation.DoesNotExist:
            raise CommandError(f'No organisation found with name "Trade Remedies Investigations Directorate".')
        except Exception as e:
            raise CommandError( e )
        trade_authority_organisation.name = "Trade Remedies Authority"
        self.stdout.write(
            self.style.SUCCESS(
                'Updating Trade Authority name from "Trade Remedies Investigations Directorate" to'
                '"Trade Remedies Authority"'
            )
        )
 
        try:
            submission_document_type = SubmissionDocumentType.objects.filter(
                name="TRID Document",
            ).first()
        except SubmissionDocumentType.DoesNotExist:
            raise CommandError('No SubmissionDocumentType found with name "TRID Document".')
        except Exception as e:
            raise CommandError( e )
        submission_document_type.name = "TRA Document"
        self.stdout.write(
            self.style.SUCCESS(
                'Updating SubmissionDocumentType name from "TRID Document" to "TRA Document"'
            )
        )

        try:
            job_title = JobTitle.objects.filter(
                name="TRID Other",
            ).first()
        except JobTitle.DoesNotExist:
            raise CommandError('No JobTitle found with name "TRID Other".')
        except Exception as e:
            raise CommandError( e )
        job_title.name = "TRA Other"
        self.stdout.write(
            self.style.SUCCESS(
                'Updating JobTitle name from "TRID Other" to "TRA Other"'
            )
        )

        """
        try:
            case_stage = CaseStage.objects.filter(
                label="TRID approval of the decision",
            ).first()
        except CaseStage.DoesNotExist:
            raise CommandError('No CaseStage found with label "TRID approval of the decision".')
        except Exception as e:
            raise CommandError( e )
        case_stage.label = "TRA approval of the decision"
        self.stdout.write(
            self.style.SUCCESS(
                'Updating WorkflowTemplate from "TRID approval of the decision"'
                ' to "TRA approval of the decision"'
            )
        )
        try:
            workflow_template = WorkflowTemplate.objects.filter(
                label="TRID approval of the decision",
            ).first()
        except WorkflowTemplate.DoesNotExist:
            raise CommandError('No WorkflowTemplate found with label "TRID approval of the decision".')
        except Exception as e:
            raise CommandError( e )
        workflow_template.name = "TRA approval of the decision"
        self.stdout.write(
            self.style.SUCCESS(
                'Updating WorkflowTemplate from "TRID approval of the decision"'
                ' to "TRA approval of the decision"'
            )
        )
        """


        # trade_authority_organisation.save()
        # submission_document_type.save()
        # workflow_template_
        # job_title.save()
        return
