import base64
import json
from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIRequestFactory
from django.test import override_settings


from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation
from organisations.services.v2.views import OrganisationViewSet
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
        fat_response = self.client.get(f"/api/v2/organisations/{self.organisation.pk}/").json()
        assert "id" in fat_response
        assert "full_country_name" in fat_response
        assert "name" in fat_response

        slim_response = self.client.get(
            f"/api/v2/organisations/{self.organisation.pk}/?slim=yes"
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

    @pytest.mark.django_db
    def test_list_viewset_fields_are_read_only(self):
        factory = APIRequestFactory()
        url = reverse("organisations-list")

        viewset = OrganisationViewSet()

        request = factory.get(url)
        request.query_params = {}
        request.user = MagicMock()

        viewset.request = request
        viewset.action = "list"

        serializer_class = viewset.get_serializer_class()
        organisation = baker.make(
            "organisations.Organisation",
            name="Fake Company LTD",
            address="101 London, LD123",
            post_code="LD123",
            vat_number="GB123456789",
            eori_number="GB205672212000",
            duns_number="012345678",
            organisation_website="www.fakewebsite.com",
        )

        serializer = serializer_class([organisation], many=True)
        assert all([value.read_only for _, value in serializer_class().get_fields().items()])
        assert serializer.data[0]["name"] == "Fake Company LTD"

    @pytest.mark.django_db
    def test_slim_serializer_also_read_only(self):
        """Tests that when you pass slim in the ViewSet with a
        get request it returns a read only serializer.
        """
        factory = APIRequestFactory()
        url = reverse("organisations-list")

        viewset = OrganisationViewSet()

        request = factory.get(url)
        request.query_params = {"slim": "yes"}
        request.user = MagicMock()

        viewset.request = request
        viewset.action = "list"
        serializer_class = viewset.get_serializer_class()
        assert all([value.read_only for _, value in serializer_class().get_fields().items()])
        assert "full_country_name" not in serializer_class().get_fields().keys()

    @override_settings(API_RATELIMIT_RATE="1/h")
    def test_ratelimit(self):
        # first request should be fine
        response = self.client.get("/api/v2/organisations/")
        assert response.status_code == 200

        # second request should be rate-limited
        response = self.client.get("/api/v2/organisations/")
        assert response.status_code == 429
