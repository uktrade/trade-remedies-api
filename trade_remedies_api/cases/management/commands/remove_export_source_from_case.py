import logging

from django.core.management.base import BaseCommand

from cases.models import Case, ExportSource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Remove the 'Export Source' field data from a case.
    This will change the behaviour of a case relating to 'All Countries'
    rather than a specific one."""

    # ./manage.py remove_export_source_from_case -case_name <NAME FROM CASEWORKER>

    def add_arguments(self, parser):
        parser.add_argument(
            "-case_name", type=str, help="Title of the case to update. Case Sensitive"
        )

    def handle(self, *args, **options):
        logger.info("Clearing Export Source for given case: " + options["case_name"])
        case_to_amend = Case.objects.get(name=options["case_name"])
        ExportSource.objects.filter(case=case_to_amend).delete()
        logger.info("Export Source cleared for case: " + options["case_name"])
