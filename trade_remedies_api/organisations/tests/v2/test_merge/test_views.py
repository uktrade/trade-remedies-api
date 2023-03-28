from django.contrib.auth.models import Group

from django.contrib.auth.models import Group

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.test_bases import CaseSetupTestMixin
from contacts.models import Contact
from invitations.models import Invitation
from organisations.models import SubmissionOrganisationMergeRecord
from organisations.tests.v2.test_merge import MergeTestBase
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationCaseRole
from test_functional import FunctionalTestBase


class TestOrganisationMergeRecordViewSet(MergeTestBase, FunctionalTestBase):
    def setUp(self):
        super().setUp()
        submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        self.contact = Contact.objects.create(
            name="test name",
            email="test@example.com",  # /PS-IGNORE
            organisation=self.organisation_1,
        )
        submission_status = submission_type.default_status
        self.submission_object = Submission.objects.create(
            name="Invite 3rd party",
            type=submission_type,
            status=submission_status,
            case=self.case_object,
            contact=self.contact_object,
            organisation=self.organisation,
        )
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=Group.objects.get(name=SECURITY_GROUP_ORGANISATION_USER),
            name="test name",
            email="test@example.com",  # /PS-IGNORE
            organisation=self.organisation,
            case=self.case_object,
            user=self.user,
            submission=self.submission_object,
            contact=self.contact_object,
            created_by=self.user,
        )

    def test_submission_organisation_merge_record_creation(self):
        """Passing a submission_id query parameter creates a
        new SubmissionOrganisationMergeRecord object.
        """
        assert not SubmissionOrganisationMergeRecord.objects.filter(
            submission=self.submission_object,
            organisation_merge_record=self.merge_record,
        ).exists()
        self.client.get(
            f"/api/v2/organisation_merge_records/{self.merge_record.pk}/?submission_id={self.submission_object.pk}"
        )
        assert SubmissionOrganisationMergeRecord.objects.filter(
            submission=self.submission_object,
            organisation_merge_record=self.merge_record,
        ).exists()

    def test_reset_duplicates(self):
        """Tests that reset method on the viewset resets all potential duplicates"""
        self.merge_record.potential_duplicates().update(
            status="attributes_selected", child_fields=["name"], parent_fields=["address"]
        )
        response = self.client.patch(
            f"/api/v2/organisation_merge_records/{self.merge_record.pk}/reset/"
        ).json()
        assert all([each["status"] == "pending" for each in response["potential_duplicates"]])
        assert all([each["child_fields"] == [] for each in response["potential_duplicates"]])
        assert all([each["parent_fields"] == [] for each in response["potential_duplicates"]])

    def test_get_duplicate_cases(self):
        """Tests that get_duplicate_cases method on the viewset returns all cases that are
        shared between the parent and child organisations with different case roles."""
        response = self.client.get(
            f"/api/v2/organisation_merge_records/{self.merge_record.pk}/get_duplicate_cases/"
        ).json()
        assert response == []

        role_1 = OrganisationCaseRole.objects.create(
            organisation=self.organisation_1, case=self.case_object, role=self.applicant_case_role
        )
        role_2 = OrganisationCaseRole.objects.create(
            organisation=self.organisation_2, case=self.case_object, role=self.contributor_case_role
        )
        response = self.client.get(
            f"/api/v2/organisation_merge_records/{self.merge_record.pk}/get_duplicate_cases/"
        ).json()
        assert response == [{"case_id": self.case_object.pk, "role_ids": [role_1.pk, role_2.pk]}]
