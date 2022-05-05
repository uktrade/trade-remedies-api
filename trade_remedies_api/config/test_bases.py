from django.contrib.auth.models import Group
from django.conf import settings
from django.test import TestCase
from django.test.client import Client
from core.models import User
from security.constants import (SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER,
                                SECURITY_GROUP_THIRD_PARTY_USER)

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
        self.user = User.objects.create_user(
            email=email,
            password=password,
        )
        g1 = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        g2 = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        g3 = Group.objects.create(name=SECURITY_GROUP_THIRD_PARTY_USER)
        self.user.groups.add(g1)
        self.user.groups.add(g2)
        self.user.groups.add(g3)
        self.user.save()


class APITestBase(UserSetupTestBase):
    """Test base class that allows you to use Django TestCase.client() to test the API"""

    def get_headers(self):
        return {
            "HTTP_AUTHORIZATION": f"Token {self.user.auth_token}",
            "HTTP_X_USER_AGENT": "TEST_BROWSER",
        }

    def get_request(self, url):
        return self.client.get(url, **self.get_headers())
