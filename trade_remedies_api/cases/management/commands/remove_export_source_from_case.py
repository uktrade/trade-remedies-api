import logging

from django.core.management.base import BaseCommand

from cases.models import Case, ExportSource

from cases.constants import ALL_COUNTRY_CASE_TYPES

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Remove the 'Export Source' field data from a case.
    This will change the behaviour of a case relating to 'All Countries'
    rather than a specific one."""

    def add_arguments(self, parser):
        parser.add_argument(
            "-case_id", type=str, help="ID of the case to update. Get it from the caseworker URL."
        )

    def handle(self, *args, **options):
        logger.info("Clearing Export Source for given case: " + options["case_id"])
        case_to_amend = Case.objects.get(id=options["case_id"])
        if case_to_amend.type.id in ALL_COUNTRY_CASE_TYPES:
            ExportSource.objects.filter(case=case_to_amend).delete()
        else:
            raise Exception("Case identified is of a type not in the ALL_COUNTRY_CASE_TYPES list")

        logger.info("Export Source cleared for case: " + options["case_id"])
