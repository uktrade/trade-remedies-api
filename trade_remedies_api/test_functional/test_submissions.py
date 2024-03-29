from rest_framework.reverse import reverse
from rest_framework.test import APITransactionTestCase

from rest_framework.test import APITransactionTestCase

from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Case, CaseType, Submission, SubmissionStatus, SubmissionType
from config.test_bases import UserSetupTestBase
from test_functional import FunctionalTestBase


class TestSubmissionAPI(FunctionalTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.case_object = Case.objects.create(
            name="test case", type=CaseType.objects.get(acronym="AD")
        )
        roi_submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)

        self.submission_object = Submission.objects.create(
            case=self.case_object,
            type=roi_submission_type,
            created_by=self.user,
            status=roi_submission_type.default_status,
        )
