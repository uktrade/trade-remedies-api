from unittest.mock import patch

from config.test_bases import CaseSetupTestMixin
from documents.models import Document
from documents.services.v2.serializers import DocumentSerializer
from organisations.services.v2.serializers import (
    OrganisationSerializer,
)


class TestDocumentSerializer(CaseSetupTestMixin):
    @patch("documents.fields.S3FileField")
    def setUp(self) -> None:
        super().setUp()
        self.document = Document.objects.create(
            name="really really really really really really long name.pdf",
            file="document.pdf",
            size=1213123123,
            confidential=True,
            system=False,
            created_by=self.user,
        )
        self.serializer = DocumentSerializer(instance=self.document).data

    def test_is_uploaded_document(self):
        assert not self.serializer["is_uploaded_document"]

    def test_extension(self):
        assert self.serializer["extension"] == "pdf"

    def test_truncated_name(self):
        assert self.serializer["truncated_name"] == "really really real...ally long name.pdf"

    def test_size_in_kb(self):
        assert self.serializer["size_in_kb"] == "1,184,691"
