import base64
import json

from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation
from test_functional import FunctionalTestBase


class TestBaseModelViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def test_filter_parameters_queryset(self):
        """
        Tests that filter_parameters can be passed as a base64-encoded json string to filter the
        queryset."""
        Organisation.objects.create(name="filter_1"),
        organisations = self.client.get("/api/v2/organisations/").json()
        assert len(organisations) == 2
        assert organisations[1]["name"] == self.organisation.name

        # now lets filter
        organisations = self.client.get(
            f"""/api/v2/organisations/?filter_parameters={base64.urlsafe_b64encode(json.dumps({
                "name": "filter_1"
            }).encode()).decode()}"""
        ).json()
        assert len(organisations) == 1
        assert organisations[0]["name"] == "filter_1"

        # try filtering with a non-existent company
        organisations = self.client.get(
            f"""/api/v2/organisations/?filter_parameters={base64.urlsafe_b64encode(json.dumps({
                "name": "dont exist"
            }).encode()).decode()}"""
        ).json()
        assert len(organisations) == 0

    def test_slim(self):
        """Tests that when the 'slim' query parameter is passed, a slimmed-down of the serializer is
        used.
        """
        fat_response = self.client.get(f"/api/v2/organisations/{self.organisation.pk}").json()
        assert "id" in fat_response
        assert "full_country_name" in fat_response
        assert "name" in fat_response

        slim_response = self.client.get(
            f"/api/v2/organisations/{self.organisation.pk}?slim=yes"
        ).json()
        assert "id" in slim_response
        assert "full_country_name" not in slim_response
        assert "name" in slim_response

    def test_deleted_item(self):
        case = self.client.get(f"/api/v2/cases/{self.case_object.id}/")
        assert case.status_code == 200

        self.case_object.delete()
        case = self.client.get(f"/api/v2/cases/{self.case_object.id}/")
        assert case.status_code == 404

    def test_deleted_items(self):
        case = self.client.get("/api/v2/cases/")
        assert case.status_code == 200
        assert len(case.json()) == 1

        self.case_object.delete()
        case = self.client.get("/api/v2/cases/")
        assert case.status_code == 200
        assert len(case.json()) == 0
