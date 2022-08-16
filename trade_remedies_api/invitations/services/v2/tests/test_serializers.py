from django.contrib.auth.models import Group
from django.test import TestCase

from config.test_bases import OrganisationSetupTestMixin, UserSetupTestBase
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER


class TestInvitationSerializer(OrganisationSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER),
            name="test name",
            email="test@example.com",
        )

    def test_security_group(self):
        serializer = InvitationSerializer(self.invitation_object)
        self.assertEqual(
            serializer.data["organisation_security_group"],
            SECURITY_GROUP_ORGANISATION_USER
        )

    def test_correct_data(self):
        serializer = InvitationSerializer(self.invitation_object)
        self.assertEqual(
            serializer.data["name"],
            "test name"
        )
        self.assertEqual(
            serializer.data["email"],
            "test@example.com"
        )
