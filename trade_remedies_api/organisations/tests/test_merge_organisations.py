from django.contrib.auth.models import Group
from django.test import TestCase

from cases.constants import CASE_ROLE_DOMESTIC_PRODUCER
from cases.models import Case
from core.models import User
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER
from security.models import CaseRole, OrganisationUser


class TestMergeOrganisations(TestCase):
    def setUp(self) -> None:
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        CaseRole.objects.create(key="domestic_producer")

        # creating the orgs
        self.parent_organisation = Organisation.objects.create(
            name="Parent Organisation",
            address="1 parent org road",
            post_code="1234",
            vat_number="BH3142134",
            organisation_website="www.example.com",
        )
        self.child_organisation = Organisation.objects.create(
            name="Child Organisation",
            address="1 child org road",
            post_code="1234",
            vat_number="BH3142134",
            organisation_website="www.child.example.com",
        )

        # creating some cases
        self.first_case_object = Case.objects.create(name="first case object")
        self.second_case_object = Case.objects.create(name="first case object")

        # now we associate some users with each org
        self.parent_owner = User.objects.create(
            email="parent_owner@example.com",  # /PS-IGNORE
            name="parent owner",
        )
        self.parent_owner_contact = self.parent_owner.contact
        self.parent_owner_org_user = self.parent_organisation.assign_user(
            user=self.parent_owner,
            security_group=SECURITY_GROUP_ORGANISATION_OWNER,
        )

        self.child_owner = User.objects.create(
            email="child_owner@example.com",  # /PS-IGNORE
            name="child owner",
        )
        self.child_owner_contact = self.child_owner.contact
        self.child_owner_org_user = self.child_organisation.assign_user(
            user=self.child_owner,
            security_group=SECURITY_GROUP_ORGANISATION_OWNER,
        )

        # assigning cases
        self.parent_organisation.assign_case(
            case=self.first_case_object,
            role="domestic_producer",
        )
        self.parent_owner.assign_to_case(
            case=self.first_case_object, organisation=self.parent_organisation
        )

        self.child_organisation.assign_case(
            case=self.second_case_object,
            role="domestic_producer",
        )
        self.child_owner.assign_to_case(
            case=self.second_case_object, organisation=self.child_organisation
        )

    def test_normal_merge(self):
        # Tests that a normal merge (without weird edge cases) takes place as normal)
        Organisation.objects.merge_organisations(self.parent_organisation, self.child_organisation)

        assert self.child_organisation.deleted_at
        assert not OrganisationUser.objects.filter(organisation=self.child_organisation).exists()
