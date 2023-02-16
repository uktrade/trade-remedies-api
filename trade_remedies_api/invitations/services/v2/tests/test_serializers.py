from django.utils import timezone

from cases.constants import SUBMISSION_DOCUMENT_TYPE_CUSTOMER, SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, SubmissionDocumentType, get_submission_type
from config.test_bases import CaseSetupTestMixin
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import CaseRole


class InvitationCreationTest(CaseSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=self.user_group,
            name="test name",
            email="test@example.com",  # /PS-IGNORE
        )


class TestInvitationSerializer(InvitationCreationTest):
    def test_security_group(self):
        serializer = InvitationSerializer(self.invitation_object)
        self.assertEqual(
            serializer.data["organisation_security_group"], SECURITY_GROUP_ORGANISATION_USER
        )

    def test_correct_data(self):
        serializer = InvitationSerializer(self.invitation_object)
        self.assertEqual(serializer.data["name"], "test name")
        self.assertEqual(serializer.data["email"], "test@example.com")  # /PS-IGNORE

    def test_case_role_key(self):
        applicant_case_role = CaseRole.objects.create(name="Applicant", key="applicant")
        serializer = InvitationSerializer(
            instance=self.invitation_object, data={"case_role_key": "applicant"}
        )
        assert serializer.is_valid()
        assert serializer.validated_data["case_role"] == applicant_case_role

    def test_draft_status(self):
        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.is_valid()
        assert serializer.validated_data["status"] == ("draft", "Draft")

    def test_accepted_status(self):
        self.invitation_object.invitation_type = 1
        self.invitation_object.accepted_at = timezone.now()
        self.invitation_object.email_sent = True
        self.invitation_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("accepted", "Accepted")

    def test_invite_sent_status(self):
        self.invitation_object.invitation_type = 1
        self.invitation_object.email_sent = True
        self.invitation_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("invite_sent", "Invite sent")


class TestRepresentativeInvitationSerializer(InvitationCreationTest):
    def setUp(self) -> None:
        super().setUp()
        SubmissionDocumentType.objects.create(
            id=SUBMISSION_DOCUMENT_TYPE_CUSTOMER, key="respondent", name="Customer Document"
        )

        self.submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        submission_status = self.submission_type.default_status
        self.submission_object = Submission.objects.create(
            name="Invite 3rd party",
            type=self.submission_type,
            status=submission_status,
            case=self.case_object,
            contact=self.contact_object,
            organisation=self.organisation,
        )
        self.invitation_object.invitation_type = 2
        self.invitation_object.submission = self.submission_object
        self.invitation_object.save()

    def test_invite_waiting_tra_review_status(self):
        self.invitation_object.email_sent = True
        self.invitation_object.save()
        self.submission_object.status = self.submission_type.received_status
        self.submission_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("waiting_tra_review", "Waiting TRA Approval")

    def test_invite_rejected_by_tra_status(self):
        self.invitation_object.email_sent = True
        self.invitation_object.rejected_at = timezone.now()
        self.invitation_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("rejected_by_tra", "Rejected by the TRA")

    def test_invite_approved_by_tra_status(self):
        self.submission_object.save()

        self.invitation_object.email_sent = True
        self.invitation_object.approved_at = timezone.now()
        self.invitation_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("approved_by_tra", "Approved by the TRA")

    def test_invite_submission_deficient_status(self):
        self.submission_object.status = self.submission_type.deficient_status
        self.submission_object.save()
        self.invitation_object.email_sent = True
        self.invitation_object.approved_at = timezone.now()
        self.invitation_object.save()

        serializer = InvitationSerializer(instance=self.invitation_object)
        assert serializer.data["status"] == ("deficient", "Deficient")
