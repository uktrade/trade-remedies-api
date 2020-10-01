from django.test import TestCase
from invitations.models import Invitation
from contacts.models import Contact
from cases.models import Case
from core.models import User
from organisations.models import Organisation
from security.models import CaseRole
from django.contrib.auth.models import Group
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    ROLE_APPLICANT,
)


PASSWORD = "A7Hhfa!jfaw@f"


class InviteTest(TestCase):
    fixtures = ["roles.json", "actions.json"]

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        self.case_role = CaseRole.objects.get(id=ROLE_APPLICANT)
        self.caseworker = User.objects.create(email="case@worker.com", name="Case Worker")
        self.user = User.objects.create_user(
            name="Test User",
            email="standard@test.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.case = Case.objects.create(name="Test Case", created_by=self.user)
        self.organisation = Organisation.objects.create(name="Test Org")
        self.contact_1 = Contact.objects.create(name="Test User", email="standard@test.com")
        self.contact_2 = Contact.objects.create(name="Other User", email="nonstandard@test.com")

    def test_invite_different_person(self):
        """
        Test a scenario where invited user is different than the contact invited
        """
        invite = Invitation.objects.create(
            created_by=self.caseworker,
            contact=self.contact_2,
            user=self.user,
            case=self.case,
            organisation=self.organisation,
            case_role=self.case_role,
        )
        deviate, diff = invite.compare_user_contact()
        assert deviate
        assert "email" in diff
        assert "name" in diff

    def test_invite_same_person(self):
        """
        Test a scenario where invited user is the same as than the contact invited
        """
        invite = Invitation.objects.create(
            created_by=self.caseworker,
            contact=self.contact_1,
            user=self.user,
            case=self.case,
            organisation=self.organisation,
            case_role=self.case_role,
        )
        deviate, diff = invite.compare_user_contact()
        assert not deviate
        assert not diff
