from config.test_bases import CaseSetupTestMixin
from invitations.models import Invitation
from organisations.services.v2.serializers import OrganisationSerializer
from security.models import CaseRole


class TestOrganisationSerializer(CaseSetupTestMixin):
    def test_normal(self):
        serializer = OrganisationSerializer(instance=self.organisation)
        assert not serializer.data["cases"]
        assert not serializer.data["organisationuser_set"]
        assert not serializer.data["invitations"]

    def test_organisationuser_set(self):
        self.organisation_user = self.organisation.assign_user(
            user=self.user, security_group=self.owner_group
        )
        serializer = OrganisationSerializer(instance=self.organisation)
        assert serializer.data["organisationuser_set"]
        assert len(serializer.data["organisationuser_set"]) == 1
        assert serializer.data["organisationuser_set"][0]["id"] == str(self.organisation_user.id)

    def test_cases(self):
        self.organisation.assign_user(user=self.user, security_group=self.owner_group)
        self.case_object.assign_user(
            self.user, created_by=self.user, organisation=self.organisation, relax_security=True
        )
        serializer = OrganisationSerializer(instance=self.organisation)
        assert serializer.data["cases"]
        assert len(serializer.data["cases"]) == 1
        assert serializer.data["cases"][0]["id"] == str(self.case_object.id)

    def test_invitations(self):
        invitation = Invitation.objects.create_user_invite(
            user_email="invite_me@example.com",  # /PS-IGNORE
            organisation=self.organisation,
            invited_by=self.user,
            meta={
                "name": "invite me name",
            },
        )
        serializer = OrganisationSerializer(instance=self.organisation)
        assert serializer.data["invitations"]
        assert len(serializer.data["invitations"]) == 1
        assert serializer.data["invitations"][0]["id"] == str(invitation.id)

class TestOrganisationCaseRoleSerializer(CaseSetupTestMixin):
    def test_normal(self):
        pass
