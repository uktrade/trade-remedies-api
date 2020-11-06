import logging

from cases.models import CaseWorkflowState, CaseWorkflow
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Reset all case workflows. Careful with this one as it will erase all case workflows."

    def handle(self, *args, **options):
        logger.info("+ Deleting case workflow state")
        CaseWorkflowState.objects.all().delete()
        logger.info("+ Deleting case workflows")
        CaseWorkflow.objects.all().delete()
