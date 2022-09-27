from config.test_bases import OrganisationSetupTestMixin
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer
from security.constants import SECURITY_GROUP_ORGANISATION_USER


class TestInvitationSerializer(OrganisationSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=self.user_group,
            name="test name",
            email="test@example.com",  # /PS-IGNORE
            created_by=self.user,
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

    def test_created_by_tra_false(self):
        serializer = InvitationSerializer(self.invitation_object)
        assert not serializer.data["is_created_by_tra"]

    def test_created_by_tra_true(self):
        self.user.groups.add(self.tra_administrator_group)
        self.user.save()
        serializer = InvitationSerializer(self.invitation_object)
        assert serializer.data["is_created_by_tra"]

    def test_created_by_name_email(self):
        serializer = InvitationSerializer(self.invitation_object)
        assert serializer.data["created_by_name"] == self.user.name
        assert serializer.data["created_by_email"] == self.user.email
