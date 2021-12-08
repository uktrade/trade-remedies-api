import logging

from django.core.management.base import BaseCommand, CommandError

from audit.models import Audit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Update all audit log items to include a pre-computed case_title "
        "in order to improve audit log download time."
    )

    def handle(self, *args, **options):
        """Command handler.

        Accessing the audit case_title property forces it to be precomputed
        and stored in the json field data attribute. We call save on each model
        to persist.
        """
        logger.info("Patching audit log")
        count = Audit.objects.all().count()
        audits = Audit.objects.all().iterator()
        logger.info(f"Found {count} audit log entries")
        titled = 0
        logger.info("Patching case titles...")
        for audit in audits:
            if audit.case_title:
                titled += 1
            audit.save()
        logger.info(f"Precomputed case titles for {titled} audit log entries")
