import time
import datetime
from django.urls import reverse
from django.utils import timezone

from config.test_bases import APITestBase
from core.exceptions import SingleValidationAPIException
from core.models import PasswordResetRequest, TwoFactorAuth


class TestTwoFactorRequestAPI(APITestBase):
    """Tests the PasswordResetRequestSerializer class."""

    def setUp(self) -> None:
        super().setUp()

        # Creating a PasswordResetRequest object for our mock user
        self.twofactorauth = TwoFactorAuth(user=self.user)
        self.twofactorauth.generated_at = timezone.now() - datetime.timedelta(seconds=30)
        self.twofactorauth.save()

    def test_two_factor_request_too_many(self):
        """Requesting a 2fa code in quick succession should throw an error"""
        self.get_request(reverse("two_factor_request", kwargs={"delivery_type": "email"}))
        with self.assertRaises(SingleValidationAPIException):
            self.get_request(reverse("two_factor_request", kwargs={"delivery_type": "email"}))
