from django.test import TestCase
from django.contrib.auth.models import Group
from core.models import User
from organisations.models import Organisation
from cases.models.case import Case
from django.core.management import call_command

from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
)

from security.models import OrganisationCaseRole, CaseRole, UserCase

PASSWORD = "A7Hhfa!jfaw@f"


class CorrectUserContactOrgTests(TestCase):
    fixtures = [
        "tra_organisations.json",
    ]

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        self.organisation = Organisation.objects.create(name="test_organisation")
        self.case = Case.objects.create(name="test_case")

        example_role = CaseRole.objects.create(name="test_role")
        CaseRole.objects.create(key="contributor")

        OrganisationCaseRole.objects.create(organisation=self.organisation, case=self.case, role=example_role)

        self.user = User.objects.create_user(
            name="test_user",
            email="test@example.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
            country="GB",
            timezone="Europe/London",
            phone="077931231234",

        )

    def test_parameters_have_been_set_up(self):
        user_objects = User.objects.all()
        assert user_objects.count() == 1

        organisation_objects = Organisation.objects.all()
        assert organisation_objects.count() == 3

        case_objects = Case.objects.all()
        assert case_objects.count() == 1

    def test_correct_user_contact_org_works(self):
        assert not UserCase.objects.filter(case=self.case, user__organisationuser__organisation=self.organisation).exists()

        args = []
        opts = {"organisation_id": self.organisation.id, "case_id": self.case.id, "user_id": self.user.id}
        call_command(
            "correct_user_contact_org",
            *args,
            **opts
        )

        self.case.refresh_from_db()
        self.organisation.refresh_from_db()
        self.user.refresh_from_db()

        print(self.case.organisation_users(self.organisation))
        print(UserCase.objects.filter(case=self.case, user__organisationuser__organisation=self.organisation))
