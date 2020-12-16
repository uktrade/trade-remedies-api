import logging

from workflow.models import Node
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Clear workflow nodes as a pre-requisite to reloading"

    def handle(self, *args, **options):

        logger.info("+ Deleting workflow nodes")
        nodes = Node.objects.all()
        # using a raw delete because we don't want the self-reference checks getting in the way.
        nodes._raw_delete(nodes.db)
