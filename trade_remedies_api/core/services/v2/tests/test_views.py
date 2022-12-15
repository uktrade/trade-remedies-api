from config.test_bases import CaseSetupTestMixin
from contacts.models import CaseContact
from core.services.v2.users.serializers import UserSerializer
from organisations.models import Organisation
from test_functional import FunctionalTestBase


class TestContactViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def test_change_organisation(self):
        new_organisation = Organisation.objects.create(name="new org")
        self.client.patch(
            f"/api/v2/contacts/{self.contact_object.pk}/change_organisation/",
            data={"organisation_id": new_organisation.id},
        )
        self.contact_object.refresh_from_db()
        assert self.contact_object.organisation_id == new_organisation.id

    def test_add_to_case(self):
        assert not CaseContact.objects.filter(
            case=self.case_object, contact=self.contact_object, organisation=self.organisation
        )
        self.client.patch(
            f"/api/v2/contacts/{self.contact_object.pk}/add_to_case/",
            data={"organisation_id": self.organisation.id, "case_id": self.case_object.id},
        )
        assert CaseContact.objects.filter(
            case=self.case_object, contact=self.contact_object, organisation=self.organisation
        )
