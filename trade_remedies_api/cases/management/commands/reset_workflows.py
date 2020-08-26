from cases.models import CaseWorkflowState, CaseWorkflow
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = "Reset all case workflows. Careful with this one as it will erase all case workflows."

    def handle(self, *args, **options):
        print("+ Deleting case workflow state")
        CaseWorkflowState.objects.all().delete()
        print("+ Deleting case workflows")
        CaseWorkflow.objects.all().delete()
