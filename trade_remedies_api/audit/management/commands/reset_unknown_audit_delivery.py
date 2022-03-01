import logging

from django.core.management.base import BaseCommand, CommandError

from audit.models import Audit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Update all NOTIFY audit logs where their status is not in ('delivered', 'unknown', 'permanent-failure'," 
        "'temporary-failure') to change their status to 'unknown-changed'"
    )

    def handle(self, *args, **options):
        """Command handler.

        A temporary fix to TRSV2-134. Updating all Audit logs with type NOTIFY which don't have a 'status' key in
        their 'data' JSON column. Change their status to 'unknown-changed' so they're not constantly checked against the
        GOV.NOTIFY API
        """
        pass