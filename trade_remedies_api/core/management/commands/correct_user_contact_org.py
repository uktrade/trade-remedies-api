from django.core.management import BaseCommand

from core.models import User
from cases.models import Case
from organisations.models import Organisation
from security.models import OrganisationCaseRole, CaseRole, CaseAction, UserCase
from django.utils import timezone


class Command(BaseCommand):

    help = "Fixes issues regarding the user case role and organisation assignment"

    def add_arguments(self, parser):
        parser.add_argument("organisation_id", nargs=1, type=str)
        parser.add_argument("case_id", nargs=1, type=str)
        parser.add_argument("user_id", nargs=1, type=str)

    def handle(self, *args, **options):
        organisation_id = options["organisation_id"]
        case_id = options["case_id"]
        user_id = options["user_id"]

        organisation = Organisation.objects.get(pk=organisation_id)
        case = Case.objects.get(pk=case_id)
        user = User.objects.get(pk=user_id)

        roles = CaseRole.objects.all()
        contributor_role = roles[7]

        UserCase.objects.filter(case=case, user__organisationuser__organisation=case)
        case.assign_organisation_user(user, organisation)
        case.organisation_users(organisation)

        user.contact.organisation = organisation
        user.contact.save()
        user.refresh_from_db()

        OrganisationCaseRole.objects.get_organisation_role(case=case, organisation=organisation)

        user_ocr = OrganisationCaseRole.objects.assign_organisation_case_role(organisation, case, contributor_role)[0]

        OrganisationCaseRole.objects.get_organisation_role(case=case, organisation=organisation)

        Case.objects.all_user_cases(user)
        user_ocr.approved_by = None
        user_ocr.approved_at = timezone.now()
        user_ocr.save()

        self.stdout.write(f"User {user} has been corrected")
