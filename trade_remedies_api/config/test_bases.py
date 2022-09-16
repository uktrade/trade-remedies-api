from django.contrib.auth.models import Group
from django.test import TestCase

from cases.models import Case
from core.models import User
from organisations.models import Organisation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)

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
        self.organisation = Organisation.objects.create(name="test company")


class CaseSetupTestMixin(OrganisationSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        self.case_object = Case.objects.create(name="test case")
