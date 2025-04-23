from django.core.management.base import BaseCommand, CommandError
from organisations.models import Organisation
from cases.models import Case
from security.models import OrganisationCaseRole, CaseRole

class Command(BaseCommand):
    help = "Assign a company to a specific case role in a case."

    def add_arguments(self, parser):
        parser.add_argument('organisation_id', type=int, help="ID of the organisation to assign.")
        parser.add_argument('case_id', type=int, help="ID of the case.")
        parser.add_argument('role_key', type=str, help="Key of the case role to assign.")

    def handle(self, *args, **options):
        organisation_id = options['organisation_id']
        case_id = options['case_id']
        role_key = options['role_key']

        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise CommandError(f"Organisation with ID {organisation_id} does not exist.")

        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            raise CommandError(f"Case with ID {case_id} does not exist.")

        try:
            role = CaseRole.objects.get(key=role_key)
        except CaseRole.DoesNotExist:
            raise CommandError(f"CaseRole with key '{role_key}' does not exist.")

        # Assign the organisation to the case role
        organisation_case_role, created = OrganisationCaseRole.objects.get_or_create(
            organisation=organisation,
            case=case,
            defaults={'role': role}
        )

        if not created:
            organisation_case_role.role = role
            organisation_case_role.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated organisation '{organisation.name}' to role '{role.name}' in case '{case.name}'."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigned organisation '{organisation.name}' to role '{role.name}' in case '{case.name}'."
                )
            )
