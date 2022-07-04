from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase

from core.models import User


class FunctionalTestBase(APITransactionTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            name="Health Check",
            email="standard@gov.uk",  # /PS-IGNORE
            password="super-secret-password1D!"
        )
        self.client.force_authenticate(user=self.user, token=self.user.get_access_token())
