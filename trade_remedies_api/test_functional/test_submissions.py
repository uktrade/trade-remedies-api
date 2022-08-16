from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Case, CaseType, Submission, SubmissionType
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

    def test_update_submission_status(self):
        response = self.client.put(
            f"/api/v2/submissions/{self.submission_object.pk}/update_submission_status/",
            data={"new_status": "received"},
        )
        print("asd")
