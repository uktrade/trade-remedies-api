from unittest.mock import patch

from django.contrib.auth.models import Group

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.test_bases import CaseSetupTestMixin
from contacts.models import CaseContact, Contact
from core.models import User
from invitations.models import Invitation
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import UserCase
from test_functional import FunctionalTestBase

new_name = "new name"
new_email = "new_email@example.com"  # /PS-IGNORE


class TestOrganisationViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def setUp(self) -> None:
        super().setUp()
        Organisation.objects.create(
            name="Test Organisation 1",
        )
        Organisation.objects.create(
            name="Test Organisation 2",
        )

    def test_search_by_company_name(self):
        response = self.client.get(
            "/api/v2/organisations/search_by_company_name/",
            data={
                "search_string": "test",
            },
        )

        matches = response.json()
        assert len(matches) == 3

    def test_search_by_company_name_exclude(self):
        response = self.client.get(
            "/api/v2/organisations/search_by_company_name/",
            data={
                "search_string": "test",
                "exclude_id": self.organisation.id,
            },
        )

        matches = response.json()
        assert len(matches) == 2
