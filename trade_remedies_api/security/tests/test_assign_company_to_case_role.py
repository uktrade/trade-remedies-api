from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from organisations.models import Organisation
from cases.models import Case
from security.models import OrganisationCaseRole, CaseRole


class AssignCompanyToCaseRoleTest(TestCase):
    fixtures = ["tra_organisations.json", "actions.json", "roles.json"]

    def setUp(self):
        # Set up initial data for the test
        self.organisation = Organisation.objects.create(name="Test Organisation")
        self.case = Case.objects.create(name="Test Case")
        self.role = CaseRole.objects.create(name="Test Role", key="test_role")

    def test_assign_company_to_case_role_success(self):
        # Test successful assignment of a company to a case role
        call_command(
            "assign_company_to_case_role",
            self.organisation.id,
            self.case.id,
            self.role.key,
        )

        organisation_case_role = OrganisationCaseRole.objects.get(
            organisation=self.organisation, case=self.case
        )
        self.assertEqual(organisation_case_role.role, self.role)

    def test_assign_company_to_case_role_update_existing(self):
        # Test updating an existing organisation-case-role relationship
        OrganisationCaseRole.objects.create(
            organisation=self.organisation, case=self.case, role=self.role
        )

        new_role = CaseRole.objects.create(name="New Role", key="new_role")
        call_command(
            "assign_company_to_case_role",
            self.organisation.id,
            self.case.id,
            new_role.key,
        )

        organisation_case_role = OrganisationCaseRole.objects.get(
            organisation=self.organisation, case=self.case
        )
        self.assertEqual(organisation_case_role.role, new_role)

    def test_assign_company_to_case_role_invalid_organisation(self):
        id_ = "550e8400-e29b-41d4-a716-446655440000"
        # Test invalid organisation ID
        with self.assertRaises(CommandError) as context:
            call_command("assign_company_to_case_role", id_, self.case.id, self.role.key)
        self.assertIn(f"Organisation with ID {id_} does not exist", str(context.exception))

    def test_assign_company_to_case_role_invalid_case(self):
        id_ = "550e8400-e29b-41d4-a716-446655440000"
        # Test invalid case ID
        with self.assertRaises(CommandError) as context:
            call_command(
                "assign_company_to_case_role", self.organisation.id, id_, self.role.key
            )
        self.assertIn(f"Case with ID {id_} does not exist", str(context.exception))

    def test_assign_company_to_case_role_invalid_role(self):
        # Test invalid role key
        with self.assertRaises(CommandError) as context:
            call_command(
                "assign_company_to_case_role",
                self.organisation.id,
                self.case.id,
                "invalid_role_key",
            )
        self.assertIn("CaseRole with key 'invalid_role_key' does not exist", str(context.exception))
