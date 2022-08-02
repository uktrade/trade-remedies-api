import json
import uuid

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import crypto
from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase
from rest_framework import status

from core.models import SystemParameter, User, PasswordResetRequest, UserProfile
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationUser


class HealthCheckTestBase(APITransactionTestCase):
    """Base class that creates a Health Check user with a token to access the API."""

    def setUp(self) -> None:
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        self.user = User.objects.create_user(
            name="Health Check",
            email="standard@gov.uk",  # /PS-IGNORE
            password="Super-Secret-Password1!",
            contact_phone="+447700900000",  # This is the GOV.UK Test Number, do not change.
        )
        self.client.force_authenticate(user=self.user, token=self.user.auth_token.key)


class TestRegistration(HealthCheckTestBase):
    def setUp(self):
        super().setUp()

        self.mock_registration_data = {
            "name": "Test",
            "email": "test@example.com",  # /PS-IGNORE
            "terms_and_conditions_accept": True,
            "password": "TestPassword123!",
            "two_factor_choice": "email",
            "mobile_country_code": "",
            "mobile": "",
            "uk_employer": "no",
            "company_name": "test",
            "address_snippet": "test street",
            "post_code": "12345",
            "company_number": "000000",
            "country": "GB",
            "company_website": "",
            "company_vat_number": "",
            "company_eori_number": "",
            "company_duns_number": "",
        }

    def test_valid_registration(self):
        assert not User.objects.filter(email="test@example.com").exists()  # /PS-IGNORE
        response = self.client.post(
            reverse("v2_registration"),
            data={"registration_data": json.dumps(self.mock_registration_data)},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email="test@example.com").exists()  # /PS-IGNORE
        new_user_object = User.objects.get(email="test@example.com")  # /PS-IGNORE
        assert UserProfile.objects.filter(user=new_user_object).exists()
        assert Organisation.objects.filter(companies_house_id="000000")
        new_organisation_object = Organisation.objects.get(companies_house_id="000000")
        assert OrganisationUser.objects.user_organisation_security_group(
            new_user_object, new_organisation_object
        )

    def test_invalid_user_already_exists(self):
        """Tests that if you try and create a user who already exists, it returns 201."""
        call_command("load_sysparams")  # Load system parameters
        call_command("notify_env")  # Load the template IDs from GOV.NOTIFY

        response = self.client.post(
            reverse("v2_registration"),
            data={"registration_data": json.dumps(self.mock_registration_data)},
        )
        new_user_object = User.objects.get(email="test@example.com")  # /PS-IGNORE
        assert str(response.data["response"]["result"]["pk"]) == str(new_user_object.pk)
        # Now we try and register them again
        response = self.client.post(
            reverse("v2_registration"),
            data={"registration_data": json.dumps(self.mock_registration_data)},
        )
        assert response.status_code == status.HTTP_201_CREATED

        # The PK returned by the view should be random and not match the new user
        assert str(response.data["response"]["result"]["pk"]) != str(new_user_object.pk)


class TestEmailVerify(HealthCheckTestBase):
    def test_success_request(self):
        assert not self.user.userprofile.email_verify_code_last_sent
        response = self.client.post(
            reverse("request_email_verify", kwargs={"user_pk": self.user.pk})
        )
        self.user.refresh_from_db()
        assert self.user.userprofile.email_verify_code_last_sent

    def test_success_post(self):
        assert not self.user.userprofile.email_verified_at
        email_verify_code = crypto.get_random_string(64)
        self.user.userprofile.email_verify_code = email_verify_code
        self.user.userprofile.save()
        response = self.client.post(
            reverse(
                "email_verify",
                kwargs={"user_pk": self.user.pk, "email_verify_code": email_verify_code},
            )
        )
        self.user.refresh_from_db()
        assert self.user.userprofile.email_verified_at
