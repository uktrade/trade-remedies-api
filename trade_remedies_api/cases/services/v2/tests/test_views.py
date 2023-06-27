import datetime

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.test_bases import CaseSetupTestMixin
from security.models import OrganisationCaseRole
from test_functional import FunctionalTestBase


class TestCaseViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def setUp(self):
        super().setUp()
        self.now = datetime.datetime.now()

    def test_get_empty_public_file(self):
        response = self.client.get(f"/api/v2/cases/{self.case_object.pk}/get_public_file/")
        assert response.status_code == 200
        public_file = response.json()

        assert len(public_file) == 0

    def test_get_public_file_not_issued_submission(self):
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

        OrganisationCaseRole.objects.create(
            organisation=self.organisation,
            case=self.case_object,
            role=self.applicant_case_role,
            sampled=True,
        )

        response = self.client.get(f"/api/v2/cases/{self.case_object.pk}/get_public_file/")
        assert response.status_code == 200
        public_file = response.json()

        assert len(public_file) == 0

    def test_get_public_file(self):
        submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        submission_status = submission_type.default_status
        self.submission_object = Submission.objects.create(
            name="Invite 3rd party",
            type=submission_type,
            status=submission_status,
            case=self.case_object,
            contact=self.contact_object,
            organisation=self.organisation,
            issued_at=self.now,
        )

        OrganisationCaseRole.objects.create(
            organisation=self.organisation,
            case=self.case_object,
            role=self.applicant_case_role,
            sampled=True,
        )

        response = self.client.get(f"/api/v2/cases/{self.case_object.pk}/get_public_file/")
        assert response.status_code == 200
        public_file = response.json()

        assert len(public_file) == 1
        assert public_file[0]["submission_name"] == "Invite 3rd party"
        assert public_file[0]["issued_at"] == self.now.isoformat()
        assert public_file[0]["organisation_name"] == self.organisation.name
        assert public_file[0]["organisation_case_role_name"] == "Applicant"
        assert public_file[0]["no_of_files"] == 0
        assert not public_file[0]["is_tra"]
