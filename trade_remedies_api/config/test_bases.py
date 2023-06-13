from django.contrib.auth.models import Group
from django.test import TestCase

from cases.models import Case, CaseType, ExportSource, Product, Sector
from contacts.models import Contact
from core.models import User
from organisations.models import Organisation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)
from security.models import CaseRole

email = "test@example.com"  # /PS-IGNORE
password = "F734!2jcjfdka-"  # /PS-IGNORE


class MockRequest:
    """A helper object used in the serializer to verify the origin of the request."""

    def __init__(self, META=None):
        self.META = META or dict()
        self.GET = dict()
        self.POST = dict()
        super().__init__()


class UserSetupTestBase(TestCase):
    """Test base class that creates a User and the necessary public groups"""

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(
            email=email,
            password=password,
        )
        self.contact_object = self.user.contact
        self.user_group = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        self.owner_group = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        self.third_party_group = Group.objects.create(name=SECURITY_GROUP_THIRD_PARTY_USER)
        self.user.groups.add(self.user_group)
        self.user.groups.add(self.owner_group)
        self.user.groups.add(self.third_party_group)
        self.user.save()


class OrganisationSetupTestMixin(UserSetupTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.organisation = Organisation.objects.create(name="test company", country="GB")


class CaseSetupTestMixin(OrganisationSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()

        self.applicant_case_role = CaseRole.objects.create(key="applicant", name="Applicant")
        self.contributor_case_role = CaseRole.objects.create(key="contributor", name="Contributor")
        self.rejected_case_role = CaseRole.objects.create(key="rejected", name="Rejected")
        self.preparing_case_role = CaseRole.objects.create(key="preparing", name="Preparing")
        self.awaiting_approval_case_role = CaseRole.objects.create(
            key="awaiting_approval", name="Awaiting Approval"
        )

        self.case_type_object = CaseType.objects.create(name="")
        self.case_object = Case.objects.create(
            name="test case",
            type=self.case_type_object,
        )
        self.sector_object = Sector.objects.create(name="sector", code="sector")
        self.export_source_object = ExportSource.objects.create(country="GB", case=self.case_object)
        self.product_object = Product.objects.create(
            sector=self.sector_object, name="product", case=self.case_object
        )
