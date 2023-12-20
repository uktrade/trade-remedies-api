import logging

from security.utils import create_groups, assign_group_permissions
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reset all security groups and their permission assignments"

    def handle(self, *args, **options):
        logger.info("+ Asserting all groups")
        create_groups()
        logger.info("+ Assigning permissions to groups")
        assign_group_permissions()
