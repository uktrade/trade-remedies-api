from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase

from core.models import User
from security.constants import SECURITY_GROUP_SUPER_USER


class FunctionalTestBase(APITransactionTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            name="Health Check",
            email="standard@gov.uk",  # /PS-IGNORE
            password="super-secret-password1D!",
        )
        super_user_group = Group.objects.create(name=SECURITY_GROUP_SUPER_USER)
        self.user.groups.add(super_user_group)
        self.client.force_authenticate(user=self.user, token=self.user.get_access_token())
