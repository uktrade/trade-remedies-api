from config.test_bases import OrganisationSetupTestMixin
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import CaseRole


class TestInvitationSerializer(OrganisationSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=self.user_group,
            name="test name",
            email="test@example.com",  # /PS-IGNORE
        )

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
