from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from security.models import CaseRole


class NewCaseRoleTest(TestCase):
    # seed db with CaseAction and CaseRole data - both
    # required in management command
    fixtures = ["actions.json", "roles.json"]

    def test_new_case_role_missing_argument(self):
        # No value given for (required) 'order' argument
        new_case_role = [
            "Test Role",
            "Test Roles",
            "test_role",
        ]
        with self.assertRaises(CommandError):
            call_command("new_case_role", new_case_role)

    def test_new_case_role_created(self):
        # confirm that CaseRole data exists, but no "Test Role"
        assert CaseRole.objects.all().count() > 0
        assert CaseRole.objects.filter(name="Test Role").count() == 0

        # create new case role and test that it exists in db
        new_case_role = [
            "Test Role",
            "Test Roles",
            "test_role",
            15,
        ]
        call_command("new_case_role", new_case_role)

        assert CaseRole.objects.filter(name="Test Role").count() == 1

    def test_case_role_orders_are_amended(self):
        # confirm "Domestic Producer" order value is currently 2
        pre_amend_case_role = CaseRole.objects.get(name="Domestic Producer")
        assert pre_amend_case_role.order == 2

        # create new case role and amend pre-existing "order" values,
        # multiplying by factor of 10
        new_case_role = [
            "Test Role",
            "Test Roles",
            "test_role",
            15,  # order
        ]
        call_command("new_case_role", new_case_role, factor=10)

        # Domestic Producer had order value 2. So new value will be 20.
        amended_case_role = CaseRole.objects.get(name="Domestic Producer")
        new_case_role = CaseRole.objects.get(name="Test Role")

        assert amended_case_role.order == 20
        assert new_case_role.order == 15
