import base64
import json

from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationSerializer
from test_functional import FunctionalTestBase


class TestBaseSerializer(CaseSetupTestMixin, FunctionalTestBase):
    def test_normal(self):
        serializer = OrganisationSerializer(self.organisation)
        assert serializer.data["full_country_name"] == "United Kingdom"

    def test_slim(self):
        serializer = OrganisationSerializer(self.organisation, slim=True)
        assert "full_country_name" not in serializer.data
