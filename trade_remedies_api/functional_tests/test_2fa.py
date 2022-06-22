from django.core.management import call_command
from django.urls import reverse

from core.models import TwoFactorAuth
from functional_tests.test_registration import HealthCheckTestBase


class TestTwoFactorRequest(HealthCheckTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.user.twofactorauth = TwoFactorAuth(user=self.user)
        self.user.save()

    def test_success_request(self):
        call_command('load_sysparams')  # Load system parameters
        call_command('notify_env')  # Load the template IDs from GOV.NOTIFY

        response = self.client.get(reverse(
            "two_factor_request", kwargs={"delivery_type": TwoFactorAuth.SMS})
        )
        assert response.status_code == 200
        assert self.user.twofactorauth.code in response.data["response"]["result"]["content"][
            "body"]

    def test_success_validate(self):
        response = self.client.post(
            reverse("two_factor_verify"),
            data={"2fa_code": self.user.twofactorauth.generate_code()}
        )
        assert response.status_code == 200
        assert response.data["response"]["result"]["email"] == "standard@gov.uk"  # /PS-IGNORE

    def test_unsuccessful_validate(self):
        response = self.client.post(
            reverse("two_factor_verify"),
            data={"2fa_code": "incorrect_code"}
        )
        assert response.status_code != 200
