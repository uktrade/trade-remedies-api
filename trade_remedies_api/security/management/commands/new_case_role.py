import logging

from django.core.management.base import BaseCommand
from security.models import CaseRole, CaseAction

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Add new CaseRole"

    def add_arguments(self, parser):
        # Positional aruguments - order in which they need to be entered
        # Note: using nargs paramater causes the data to be passed in a list
        parser.add_argument(
            "name", type=str, help='CaseRole name. E.g., "Overseas Producer"'
        )
        parser.add_argument(
            "plural", type=str, help='CaseRole plural. E.g., "Overseas Producers"'
        )
        parser.add_argument(
            "key", type=str, help="CaseRole key. E.g., overseas_producer"
        )
        parser.add_argument("order", type=int, help="CaseRole order. E.g., 45")

        # Optional aruguments
        parser.add_argument("--factor", type=int, help='To multiple "order" value by')

    def handle(self, *args, **options):

        if options["factor"]:
            # Increase gap between existing "order" values to make (possible) future
            # insertions easier.
            logger.info(f"Amending order values.")
            for case_role in CaseRole.objects.all():
                case_role.order *= options["factor"]
                case_role.save()

        logger.info(f"Creating new case role: {options['name']}")
        new_case_role = CaseRole.objects.create(
            name=options["name"],
            plural=options["plural"],
            key=options["key"],
            order=options["order"],
        )

        # get case actions and add to case role
        view_application = CaseAction.objects.get(id="VIEW_APPLICATION")
        view_case = CaseAction.objects.get(id="VIEW_CASE")
        new_case_role.actions.add(view_application, view_case)
