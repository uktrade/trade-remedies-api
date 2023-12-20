import logging

from django.core.management.base import BaseCommand

from cases.tasks import process_timegate_actions

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process the timegate actions that are queued and due."

    def handle(self, *args, **options):
        logger.info("+ Processing timegate actions")
        process_timegate_actions()
        logger.info("+ Completed processing timegate actions")
