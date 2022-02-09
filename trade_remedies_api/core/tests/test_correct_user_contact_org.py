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

        OrganisationCaseRole.objects.create(
            organisation=self.organisation, case=self.case, role=example_role
        )

        self.user = User.objects.create_user(
            name="test_user",
            email="test@example.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
            country="GB",
            timezone="Europe/London",
            phone="077931231234",
        )

    def test_parameters_are_set(self):
        user_objects = User.objects.all()
        assert user_objects.count() == 1

        organisation_objects = Organisation.objects.all()
        assert organisation_objects.count() == 3

        case_objects = Case.objects.all()
        assert case_objects.count() == 1

    def test_user_contact_org_is_corrected(self):
        assert not UserCase.objects.filter(
            case=self.case, organisation=self.organisation
        ).exists()
        assert self.user.contact.organisation is None

        args = []
        opts = {
            "organisation_id": [self.organisation.id],
            "case_id": [self.case.id],
            "user_id": [self.user.id],
        }
        call_command("correct_user_contact_org", *args, **opts)
        self.user.refresh_from_db()

        assert (
            UserCase.objects.filter(
                case=self.case, organisation=self.organisation
            ).count()
            == 1
        )
        assert self.user.contact.organisation.name == "test_organisation"

        # Assert the organisation case role hasn't been changed
        assert (
            OrganisationCaseRole.objects.get(
                organisation=self.organisation, case=self.case
            ).role.name
            == "test_role"
        )
