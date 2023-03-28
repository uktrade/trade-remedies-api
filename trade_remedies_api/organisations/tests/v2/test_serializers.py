from model_bakery import baker

from config.test_bases import CaseSetupTestMixin
from invitations.models import Invitation
from organisations.services.v2.serializers import (
    OrganisationCaseRoleSerializer,
    OrganisationSerializer,
)
from security.models import CaseRole, OrganisationCaseRole


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
        OrganisationCaseRole.objects.create(
            organisation=self.organisation,
            case=self.case_object,
            role=CaseRole.objects.get(key="applicant"),
        )
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

    def test_duplicate_organisations(self):
        target_organisation = baker.make(
            "organisations.Organisation",
            name="Fake Company LTD",
            address="101 London, LD123",
            post_code="LD123",
            vat_number="GB123456789",
            eori_number="GB205672212000",
            duns_number="012345678",
            organisation_website="www.fakewebsite.com",
        )

        baker.make("organisations.Organisation", name=target_organisation.name)
        baker.make(
            "organisations.Organisation",
            address=target_organisation.address,
            post_code=target_organisation.post_code,
        )
        serializer = OrganisationSerializer(instance=target_organisation)
        assert serializer.data["potential_duplicate_organisations"]
        assert len(serializer.data["potential_duplicate_organisations"]) == 2


class TestOrganisationCaseRoleSerializer(CaseSetupTestMixin):
    def test_role_key_conversion(self):
        """Tests that passing role_key in post data gets converted to CaseRole object"""
        new_org_case_role, _ = OrganisationCaseRole.objects.assign_organisation_case_role(
            organisation=self.organisation, case=self.case_object, role=self.applicant_case_role
        )
        assert new_org_case_role.role == self.applicant_case_role
        serializer = OrganisationCaseRoleSerializer(
            new_org_case_role, data={"role_key": "contributor"}
        )
        assert serializer.is_valid()
        new_org_case_role = serializer.save()
        assert new_org_case_role.role == self.contributor_case_role

    def test_get_case(self):
        org_case_role = OrganisationCaseRole.objects.create(
            organisation=self.organisation,
            case=self.case_object,
            role=self.applicant_case_role,
        )
        serializer = OrganisationCaseRoleSerializer(org_case_role)
        assert serializer.data["case"]["id"] == str(self.case_object.id)
