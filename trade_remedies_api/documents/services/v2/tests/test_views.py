from unittest.mock import patch

from django.test import override_settings

from cases.constants import SUBMISSION_DOCUMENT_TYPE_CUSTOMER, SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, SubmissionDocument, SubmissionDocumentType, get_submission_type
from config.test_bases import CaseSetupTestMixin
from documents.models import Document
from test_functional import FunctionalTestBase


@override_settings(RUN_ASYNC=False)
class TestDocumentViewSet(CaseSetupTestMixin, FunctionalTestBase):

    @patch("documents.fields.S3FileField")
    def setUp(self, patched_s3_file_field) -> None:
        super().setUp()
        SubmissionDocumentType.objects.create(
            id=SUBMISSION_DOCUMENT_TYPE_CUSTOMER, key="respondent", name="Customer Document"
        )

        submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        submission_status = submission_type.default_status
        self.submission_object = Submission.objects.create(
            name="Invite 3rd party",
            type=submission_type,
            status=submission_status,
            case=self.case_object,
            contact=self.contact_object,
            organisation=self.organisation,
        )
        self.confidential_document = Document.objects.create(
            name="confidential.pdf",
            file="confidential.pdf",
            size=123,
            confidential=True,
            system=False,
            created_by=self.user,
        )
        self.non_confidential_document = Document.objects.create(
            name="non_confidential.pdf",
            file="non_confidential.pdf",
            size=123,
            confidential=False,
            system=False,
            parent=self.confidential_document,
            created_by=self.user,
        )

        # creating submission documents
        submission_document_type = SubmissionDocumentType.type_by_user(self.user)
        self.confidential_submission_document = self.submission_object.add_document(
            document=self.confidential_document,
            document_type=submission_document_type,
            issued=False,
        )
        self.non_confidential_submission_document = self.submission_object.add_document(
            document=self.non_confidential_document,
            document_type=submission_document_type,
            issued=False,
        )

    def test_replace_parent_document(self):
        response = self.client.post(
            "/api/v2/documents/",
            data={
                "type": "confidential",
                "stored_name": "replace confidential.pdf",
                "original_name": "replace confidential.pdf",
                "file_size": "234",
                "submission_id": self.submission_object.id,
                "replace_document_id": self.confidential_document.id,
                "index_and_checksum": "no",
            },
        )
        new_document = response.json()

        self.confidential_document.refresh_from_db()
        assert self.confidential_document.deleted_at
        with self.assertRaises(SubmissionDocument.DoesNotExist):
            self.confidential_submission_document.refresh_from_db()

        self.non_confidential_document.refresh_from_db()
        assert str(self.non_confidential_document.parent.id) == new_document["id"]

    def test_replace_child_document(self):
        response = self.client.post(
            "/api/v2/documents/",
            data={
                "type": "non_confidential",
                "stored_name": "replace non_confidential.pdf",
                "original_name": "replace non_confidential.pdf",
                "file_size": "234",
                "submission_id": self.submission_object.id,
                "replace_document_id": self.non_confidential_document.id,
                "index_and_checksum": "no",
            },
        )
        new_document = response.json()

        self.non_confidential_document.refresh_from_db()
        assert self.non_confidential_document.deleted_at

        with self.assertRaises(SubmissionDocument.DoesNotExist):
            self.non_confidential_submission_document.refresh_from_db()

        assert new_document["parent"] == str(self.confidential_document.id)
