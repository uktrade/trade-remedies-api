from django.core.management import BaseCommand

from core.models import User
from cases.models import Case
from organisations.models import Organisation
from security.models import OrganisationCaseRole, CaseRole, CaseAction, UserCase
from django.utils import timezone


class Command(BaseCommand):

    help = "Command to fix issues regarding the incorrect/missing user case role and organisation assignment"

    def add_arguments(self, parser):
        parser.add_argument("--organisation_id", nargs=1, type=str, help="Organisation id")
        parser.add_argument("--case_id", nargs=1, type=str, help="Case id")
        parser.add_argument("--user_id", nargs=1, type=str, help="User id")

    def handle(self, *args, **options):
        organisation_id = options["organisation_id"]
        case_id = options["case_id"]
        user_id = options["user_id"]

        # Query database for assignments
        organisation = Organisation.objects.get(pk=organisation_id)
        case = Case.objects.get(pk=case_id)
        user = User.objects.get(pk=user_id)

        roles = CaseRole.objects.all()
        contributor_role = roles[7]

        UserCase.objects.filter(case=case, user__organisationuser__organisation=organisation)
        # <QuerySet []>
        case.assign_organisation_user(user, organisation)
        # True

        case.organisation_users(organisation)
        # <QuerySet [<UserCase: User can access case>]>

        # To fix user contact org
        user.contact.organisation = organisation
        user.contact.save()
        user.refresh_from_db()

        organisation_role = OrganisationCaseRole.objects.get_organisation_role(case=case, organisation=organisation)

        # Organisation role should only be set if it doesn't already exist
        if not organisation_role:
            user_ocr = OrganisationCaseRole.objects.assign_organisation_case_role(organisation, case, contributor_role)[0]

            OrganisationCaseRole.objects.get_organisation_role(case=case, organisation=organisation)

            user_ocr.approved_by = None
            user_ocr.approved_at = timezone.now()
            user_ocr.save()

        self.stdout.write(f"User {user} has been assigned the appropriate organisation and organisation case role")
