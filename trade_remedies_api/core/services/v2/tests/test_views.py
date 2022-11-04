from config.test_bases import CaseSetupTestMixin
from core.services.v2.users.serializers import UserSerializer
from organisations.models import Organisation
from test_functional import FunctionalTestBase


class TestContactViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def test_change_organisation(self):
        new_organisation = Organisation.objects.create(
            name="new org"
        )
        self.client.patch(
            f"/api/v2/contacts/{self.contact_object.pk}/change_organisation/",
            data={"organisation_id": new_organisation.id},
        )
        assert self.contact_object.organisation_id == new_organisation.id
