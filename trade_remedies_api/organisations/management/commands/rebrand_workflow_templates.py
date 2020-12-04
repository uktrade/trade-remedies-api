from django.core.management.base import BaseCommand, CommandError
from workflow.models import WorkflowTemplate
import json

# BEST EFFORTS CODE - FOR REVIEW


class Command(BaseCommand):
    """ Implementation of a custom django-admin command.
    Reference: https://docs.djangoproject.com/en/3.1/howto/custom-management-commands/
    """

    help = (
        "Update the name and the initialism of the Trade Authority "
        "organisation in the Django Database"
        ' from "Trade Remedies Investigations Directorate" '
        'to "Trade Remedies Authority" and from '
        '"TRA" to "TRID".'
    )

    def add_arguments(self, parser):
        """ Arguments to allow:
        1) a dry run without commit (--nocommit);
        2) a full run with commit (--commit);
        3) an undo with the undo changes commited (--undo).
        The code sanity checks for an appropriate combination of arguments.
        Commits only occur if all objects are found.
        Rational for the --nocommit is to check that all will be well before committing.
        Rational for the --undo is to allow for a full dress rehearsal in advance:
         - e.g. in UAT environment.
        """

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Formulate updates and commit them to the database",
        )
        parser.add_argument(
            "--nocommit",
            action="store_true",
            help="Formulate updates but do not commit them to the database",
        )

        parser.add_argument(
            "--undo",
            action="store_true",
            help='Formulate updates to undo the "--commit" changes and commit them to the database',
        )

    def handle_undo(self):
        """ Method to undo the commit operation to facilitate dry run prior to end of year."""

        workflow_template_transition_safeguarding_review = WorkflowTemplate.objects.filter(
            name="Transition safeguarding review"
        ).first()
        if workflow_template_transition_safeguarding_review:
            old_text = json.dumps( workflow_template_transition_safeguarding_review.template )
            new_text = old_text.replace( "TRA approval of the decision", "TRID approval of the decision" )
            if new_text == old_text:
                raise CommandError( 'String "TRA approval of the decision" not found')
            workflow_template_transition_safeguarding_review.template = json.loads(new_text)

            self.stdout.write(
                self.style.SUCCESS(
                    "undo: Can update one WorkflowTemplate object with name "
                    '"Transition safeguarding review"'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "WorkflowTemplate object with name "
                    '"Transition safeguarding review" not found'
                )
            )

        workflow_template_anti_subsidy_investigation = WorkflowTemplate.objects.filter(
            name="Anti-subsidy investigation"
        ).first()
        if workflow_template_anti_subsidy_investigation:
            old_text = json.dumps( workflow_template_anti_subsidy_investigation.template )
            new_text = old_text.replace( "TRA approval of the decision", "TRID approval of the decision" )
            if new_text == old_text:
                raise CommandError( 'String "TRA approval of the decision" not found')
            workflow_template_anti_subsidy_investigation.template = json.loads(new_text)
            self.stdout.write(
                self.style.SUCCESS(
                    "undo: Can update one WorkflowTemplate object with name "
                    '"Anti-subsidy investigation"'
                )
            )
        else:
            raise CommandError(
                "WorkflowTemplate object with name "
                '"Anti-subsidy investigation" not found'
            )

        workflow_template_transitional_anti_subsidy_review = WorkflowTemplate.objects.filter(
            name="Transitional Anti-subsidy Review"
        ).first()
        if workflow_template_transitional_anti_subsidy_review:
            old_text = json.dumps( workflow_template_transitional_anti_subsidy_review.template )
            new_text = old_text.replace( "TRA approval of the decision", "TRID approval of the decision"  )
            if new_text == old_text:
                raise CommandError( 'String "TRA approval of the decision" not found')
            workflow_template_transitional_anti_subsidy_review.template = json.loads(new_text)
            self.stdout.write(
                self.style.SUCCESS(
                    "undo: Can update one WorkflowTemplate object with name "
                    '"Transitional Anti-subsidy Review"'
                )
            )
        else:
            raise CommandError(
                "WorkflowTemplate object with name "
                '"Transitional Anti-subsidy Review" not found'
            )

        self.handle_commit( workflow_template_transition_safeguarding_review,
            workflow_template_anti_subsidy_investigation,
            workflow_template_transitional_anti_subsidy_review )
        return

    def handle_lookups(self):
        """ Method to look up the objects to be updated in the database."""

        workflow_template_transition_safeguarding_review = WorkflowTemplate.objects.filter(
            name="Transition safeguarding review"
        ).first()
        if workflow_template_transition_safeguarding_review:
            old_text = json.dumps( workflow_template_transition_safeguarding_review.template )
            new_text = old_text.replace( "TRID approval of the decision", "TRA approval of the decision" )
            if new_text == old_text:
                raise CommandError( 'String "TRID approval of the decision" not found')
            workflow_template_transition_safeguarding_review.template = json.loads(new_text)
            self.stdout.write(
                self.style.SUCCESS(
                    "Can update one WorkflowTemplate object with name "
                    '"Transition safeguarding review"'
                )
            )
        else:
            raise CommandError(
                "WorkflowTemplate object with name "
                '"Transition safeguarding review" not found'
            )

        workflow_template_anti_subsidy_investigation = WorkflowTemplate.objects.filter(
            name="Anti-subsidy investigation"
        ).first()
        if workflow_template_anti_subsidy_investigation:
            old_text = json.dumps( workflow_template_anti_subsidy_investigation.template )
            new_text = old_text.replace( "TRID approval of the decision", "TRA approval of the decision" )
            if new_text == old_text:
                raise CommandError( 'String "TRID approval of the decision" not found')
            workflow_template_anti_subsidy_investigation.template = json.loads(new_text)
            self.stdout.write(
                self.style.SUCCESS(
                    "Can update one WorkflowTemplate object with name "
                    '"Anti-subsidy investigation"'
                )
            )
        else:
            raise CommandError(
                "WorkflowTemplate object with name "
                '"Anti-subsidy investigation" not found'
            )

        workflow_template_transitional_anti_subsidy_review = WorkflowTemplate.objects.filter(
            name="Transitional Anti-subsidy Review"
        ).first()
        if workflow_template_transitional_anti_subsidy_review:
            old_text = json.dumps( workflow_template_transitional_anti_subsidy_review.template )
            new_text = old_text.replace( "TRID approval of the decision", "TRA approval of the decision" )
            if new_text == old_text:
                raise CommandError( 'String "TRID approval of the decision" not found')
            workflow_template_transitional_anti_subsidy_review.template = json.loads(new_text)
            self.stdout.write(
                self.style.SUCCESS(
                    "Can update one WorkflowTemplate object with name "
                    '"Transitional Anti-subsidy Review"'
                )
            )
        else:
            raise CommandError(
                "WorkflowTemplate object with name "
                '"Anti-subsidy investigation" not found'
            )















        return workflow_template_transition_safeguarding_review, \
        workflow_template_anti_subsidy_investigation,\
        workflow_template_transitional_anti_subsidy_review

    def handle_commit(self, workflow_template_transition_safeguarding_review,
        workflow_template_anti_subsidy_investigation,
        workflow_template_transitional_anti_subsidy_review
    ):
        """ Method to handle commit and print out message about manual updates."""

        self.stdout.write(self.style.SUCCESS("Committing updates to django database"))
        try:
            workflow_template_transition_safeguarding_review.save()
            workflow_template_anti_subsidy_investigation.save()
            workflow_template_transitional_anti_subsidy_review.save()
        except Exception as e:
            raise CommandError(str(e))
        return

    def handle(self, *args, **options):
        """ Master method for the command implementing option handling logic,
        main commit and printing of reminder message about WorflowTemplate objects."""

        if options["undo"] and options["commit"]:
            raise CommandError("Cannot run with --commit and --undo")

        if options["undo"] and options["nocommit"]:
            raise CommandError("Cannot run with --nocommit and --undo")

        if options["undo"]:
            self.handle_undo()
            return

        if not options["commit"] and not options["nocommit"]:
            raise CommandError("Must run with --commit, --nocommit or --undo")

        if options["commit"] and options["nocommit"]:
            raise CommandError("Can't  run with both --commit and --nocommit")

        if options["nocommit"] or options["commit"]:
            (
                workflow_template_transition_safeguarding_review,
                workflow_template_anti_subsidy_investigation,
                workflow_template_transitional_anti_subsidy_review
            ) = self.handle_lookups()

        if options["nocommit"]:
            self.stdout.write(
                self.style.ERROR("nocommit Option selected: UPDATES NOT COMMITTED TO DATABASE")
            )
            return

        if not options["commit"]:
            return

        # do all or none
        if not (workflow_template_transition_safeguarding_review):
            raise CommandError(
                "commit:  NO UPDATES COMMITTED as not all objects "
                "that require update were found."
            )

        self.handle_commit(workflow_template_transition_safeguarding_review, workflow_template_anti_subsidy_investigation, workflow_template_transitional_anti_subsidy_review)
        return
