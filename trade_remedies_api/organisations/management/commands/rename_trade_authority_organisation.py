from django.core.management.base import BaseCommand, CommandError
from organisations.models import Organisation
from cases.models import SubmissionDocumentType
from cases.models import CaseStage
from core.models import JobTitle
# from workflow.models import WorkflowTemplate


class Command(BaseCommand):
    help = 'Update the name and the initialism of the Trade Authority organisation in the Django Database'\
    ' from "Trade Remedies Investigations Directorate" to "Trade Remedies Authority" and from '\
    '"TRA" to "TRID".'

    def add_arguments(self, parser):

        parser.add_argument(
            '--commit',
            action='store_true',
            help='Formulate updates and commit them to the database',
        )
        parser.add_argument(
            '--nocommit',
            action='store_true',
            help='Formulate updates but do not commit them to the database',
        )

        parser.add_argument(
            '--undo',
            action='store_true',
            help='Formulate updates to undo the "--commit" changes and commit them to the database',
        )



    def handle(self, *args, **options):

        if options['undo']:

            trade_authority_organisation = Organisation.objects.filter(
                    name="Trade Remedies Authority"
            ).first()
            if trade_authority_organisation:
                trade_authority_organisation.name = "Trade Remedies Investigations Directorate" 
                self.stdout.write(
                    self.style.SUCCESS(
                        'undo: Can update one SubmissionDocumentType object name from '
                        '"Trade Remedies Authority" to'
                        '"Trade Remedies Investigations Directorate"'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        'TradeAuthorityOrganisation object with name '
                                '"Trade Remedies Authority" not found'                    
                    )
                )
    
            submission_document_type = SubmissionDocumentType.objects.filter(
                name="TRA Document",
            ).first()
            if submission_document_type:
                submission_document_type.name = "TRID Document"
                self.stdout.write(
                    self.style.SUCCESS(
                        'undo: Can update one SubmissionDocumentType object name from '
                        '"TRA Document" to "TRID Document"'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR (
                        'SubmissionDocumentType object with name "TRID Document" not found' 
                    )
                )
                    
            job_title = JobTitle.objects.filter(
                name="TRA Other",
            ).first()
            if job_title:
                job_title.name = "TRID Other"
                self.stdout.write(
                    self.style.SUCCESS(
                        'undo: Can update JobTitle object name from "TRA Other" to "TRID Other"'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR (
                        'JobTitle object with name "TRA Other" not found' 
                    )
                )

            if trade_authority_organisation and submission_document_type and job_title:
                self.stdout.write(
                    self.style.SUCCESS(
                        'Committing updates for undo operation to django database' 
                    )
                )
                try:
                    trade_authority_organisation.save()
                    submission_document_type.save()
                    job_title.save()
                except Exception as e:
                    raise CommandError( str(e) )
            else:
                raise CommandError( 
                    "commit:  NO UPDATES COMMITTED as not all objects that require update were found."
                )
            return

        if not options['commit'] and not options['nocommit']:
            raise CommandError("Must run with --commit or --nocommit")

        if options['commit'] and options['nocommit']:
            raise CommandError("Can't  run with both --commit and --nocommit")

        if options['nocommit'] or options['commit']:

            trade_authority_organisation = Organisation.objects.filter(
                    name="Trade Remedies Investigations Directorate"
            ).first()
            if trade_authority_organisation:
                trade_authority_organisation.name = "Trade Remedies Authority"
                self.stdout.write(
                    self.style.SUCCESS(
                        'Can update one TradeAuthorityOrganisation object name from '
                        '"Trade Remedies Investigations Directorate" to '
                        '"Trade Remedies Authority"'
                    )
                )
            else:
                raise CommandError( 'TradeAuthorityOrganisation object with name '
                                '"Trade Remedies Investigations Directorate" not found' 
                )
        
            submission_document_type = SubmissionDocumentType.objects.filter(
                name="TRID Document",
            ).first()
            if submission_document_type:
                submission_document_type.name = "TRA Document"
                self.stdout.write(
                    self.style.SUCCESS(
                        'Can update one SubmissionDocumentType object name from "TRID Document" to "TRA Document"'
                    )
                )
            else:
                raise CommandError( 'SubmissionDocumentType object with name "TRID Document" not found' )

            job_title = JobTitle.objects.filter(
                name="TRID Other",
            ).first()
            if job_title:
                job_title.name = "TRA Other"
                self.stdout.write(
                    self.style.SUCCESS(
                        'Can update one JobTitle object name from "TRID Other" to "TRA Other"'
                    )
                )
            else:
                raise CommandError( 'JobTitle object with name "TRID Other" not found' )

        if options['nocommit']:
            self.stdout.write(
                self.style.ERROR(
                    "nocommit Option selected: UPDATES NOT COMMITTED TO DATABASE"
                )
            )
            return

        if options['commit']:
            # do all or none
            if trade_authority_organisation and submission_document_type and job_title:
                self.stdout.write(
                    self.style.SUCCESS(
                        'Committing updates to django database' 
                    )
                )
                try:
                    trade_authority_organisation.save()
                    submission_document_type.save()
                    job_title.save()
                except Exception as e:
                    raise CommandError( str(e) )
            else:
                raise CommandError( 
                    "commit:  NO UPDATES COMMITTED as not all objects that require update were found."
                )

            self.stdout.write(
                self.style.ERROR(
                    "Now please consider manual changes to the following files:\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_anti_dumping.json;\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_anti_subsidy.json;\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_safeguards.json;\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_trans_anti_dumping.json;\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_trans_anti_subsidy.json\n"
                        "- trade_remedies_api/cases/fixtures/workflow_template_trans_safeguards.json."  )
            )
            return


