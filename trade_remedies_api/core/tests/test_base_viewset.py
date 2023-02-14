import base64
import json

from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation
from test_functional import FunctionalTestBase


class CaseAPITest(CaseSetupTestMixin, FunctionalTestBase):
    def test_filter_parameters_queryset(self):
        """
        Tests that filter_parameters can be passed as a base64-encoded json string to filter the
        queryset."""
        Organisation.objects.create(name="filter_1"),
        organisations = self.client.get("/api/v2/organisations/").json()
        assert len(organisations["results"]) == 2
        assert organisations["results"][1]["name"] == self.organisation.name

        # now lets filter
        organisations = self.client.get(
            f"""/api/v2/organisations/?filter_parameters={base64.urlsafe_b64encode(json.dumps({
                "name": "filter_1"
            }).encode()).decode()}"""
        ).json()
        assert len(organisations["results"]) == 1
        assert organisations["results"][0]["name"] == "filter_1"

        # try filtering with a non-existent company
        organisations = self.client.get(
            f"""/api/v2/organisations/?filter_parameters={base64.urlsafe_b64encode(json.dumps({
                "name": "dont exist"
            }).encode()).decode()}"""
        ).json()
        assert len(organisations["results"]) == 0
