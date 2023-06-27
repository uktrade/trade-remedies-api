from unittest.mock import patch

from django.conf import settings
from rest_framework.settings import api_settings

from config.test_bases import CaseSetupTestMixin
from documents.models import Document
from documents.services.v2.serializers import DocumentSerializer


class TestDocumentSerializer(CaseSetupTestMixin):
    @patch("documents.fields.S3FileField")
    def setUp(self, patched_s3_file_field) -> None:
        super().setUp()

        # for the DocumentSerializer to work, we need to tell it not to get the URL from S3 as this
        # is a test and that will not work
        settings.REST_FRAMEWORK["UPLOADED_FILES_USE_URL"] = False
        api_settings.reload()

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
