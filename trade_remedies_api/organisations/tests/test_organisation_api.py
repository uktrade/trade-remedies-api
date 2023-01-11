from config.test_bases import OrganisationSetupTestMixin
from organisations.models import Organisation
from test_functional import FunctionalTestBase


class OrganisationAPITest(OrganisationSetupTestMixin, FunctionalTestBase):
    def test_page_parameters_queryset(self):
        """Tests that page can be passed to paginate the queryset"""
        for i in range(10):
            Organisation.objects.create(name=f"org_name_{i}")

        first_page_organisations = self.client.get("/api/v2/organisations/").json()
        second_page_organisations = self.client.get("/api/v2/organisations/?page=2").json()
        assert len(first_page_organisations["results"]) == 10
        assert len(second_page_organisations["results"]) == 1
