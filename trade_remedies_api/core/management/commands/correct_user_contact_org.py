from django.core.management import BaseCommand

from core.models import User
from cases.models import Case
from organisations.models import Organisation
from security.models import (
    OrganisationCaseRole,
    CaseRole,
    CaseAction,
    UserCase,
    OrganisationUser,
)
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from django.utils import timezone


class Command(BaseCommand):

    help = "Command to fix issues regarding the incorrect/missing user case role and organisation assignment"

    def add_arguments(self, parser):
        parser.add_argument(
            "--organisation_id", nargs=1, type=str, help="Organisation id"
        )
        parser.add_argument("--case_id", nargs=1, type=str, help="Case id")
        parser.add_argument("--user_id", nargs=1, type=str, help="User id")

    def handle(self, *args, **options):
        case = None
        user = None
        organisation = None

        # Query database for assignments
        for organisation in options["organisation_id"]:
            organisation = Organisation.objects.get(pk=organisation)
        for case in options["case_id"]:
            case = Case.objects.get(pk=case)
        for user in options["user_id"]:
            user = User.objects.get(pk=user)

        case.assign_organisation_user(user, organisation)
        # True

        # To fix user contact org
        user.contact.organisation = organisation
        user.contact.save()
        user.refresh_from_db()

        organisation_role = OrganisationCaseRole.objects.get_organisation_role(
            case=case, organisation=organisation
        )

        contributor_role = CaseRole.objects.get(key="contributor")

        # Organisation role should only be set if it doesn't already exist
        if not organisation_role:
            user_ocr = OrganisationCaseRole.objects.assign_organisation_case_role(
                organisation, case, contributor_role
            )[0]

            OrganisationCaseRole.objects.get_organisation_role(
                case=case, organisation=organisation
            )

            user_ocr.approved_by = None
            user_ocr.approved_at = timezone.now()
            user_ocr.save()

        # We want to create an OrganisationUser if they do not already exist
        organisation_user = OrganisationUser.objects.filter(
            organisation=organisation, user=user
        )

        if not organisation_user:
            OrganisationUser.objects.assign_user(
                user, organisation, security_group=SECURITY_GROUP_ORGANISATION_USER
            )

        self.stdout.write(
            f"User {user} has been assigned the appropriate organisation and organisation case role"
        )
