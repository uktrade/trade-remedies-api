from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase
from rest_framework import status

from core.models import User, PasswordResetRequest


class PasswordResetTest(APITransactionTestCase):
    def setUp(self):
        self.user = User.objects.create(
            name="Health Check",
            email="standard@gov.uk",  # /PS-IGNORE
            password="super-secret-password1!",
        )
        token = Token.objects.create(user=self.user, key="super-secret-token1!")
        self.client.force_authenticate(user=self.user, token=token)

    def test_requests_password_reset(self):
        response = self.client.get(
            f"/api/v1/accounts/password/request_reset/?email={self.user.email}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["response"] == {"success": True, "result": True}
        assert PasswordResetRequest.objects.filter(user=self.user).exists()

    def test_request_password_reset_fails_if_invalid_email(self):
        response = self.client.get(
            "/api/v1/accounts/password/request_reset/?email=notarealemailaddress"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error_summaries": [
                "Your email address needs to be in the correct format. Eg. name@example.com"  # /PS-IGNORE
            ],
            "email": [
                "Enter your email address in the correct format. Eg. name@example.com"  # /PS-IGNORE
            ],
        }

    def test_request_password_reset_fails_if_email_missing(self):
        response = self.client.get("/api/v1/accounts/password/request_reset/?email=")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error_summaries": ["Enter your email address"],
            "email": ["Enter your email address. Eg. name@example.com"],  # /PS-IGNORE
        }

    def test_no_password_reset_request_if_no_user_for_email(self):
        response = self.client.get(
            "/api/v1/accounts/password/request_reset/?email=nouser@gov.uk"  # /PS-IGNORE
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["response"] == {"success": True, "result": True}
        assert not PasswordResetRequest.objects.filter(user=self.user).exists()

    def test_requests_password_reset_again_via_request_id(self):
        self.client.get(f"/api/v1/accounts/password/request_reset/?email={self.user.email}")
        first_request_id = PasswordResetRequest.objects.get(user=self.user).request_id
        response = self.client.get(
            f"/api/v2/accounts/password/request_reset/?request_id={first_request_id}"
        )
        assert response.data["response"] == {"success": True, "result": True}
        assert (
            PasswordResetRequest.objects.filter(user=self.user)
            .exclude(request_id=first_request_id)
            .exists()
        )

    def test_request_password_reset_fails_if_no_request_for_request_id(self):
        response = self.client.get(
            "/api/v2/accounts/password/request_reset/?request_id=68f88b49-8a09-47ef-8a6c-ffbf4319aafe"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["request_id"][0] == "Request does not exist."

    def test_request_password_reset_request_id_must_be_uuid(self):
        response = self.client.get("/api/v2/accounts/password/request_reset/?request_id=")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["request_id"][0] == "Must be a valid UUID."

    def test_reset_password_using_valid_token_for_reset_request_then_invalidates_token(self):
        self.client.get(f"/api/v1/accounts/password/request_reset/?email={self.user.email}")
        reset_token = PasswordResetRequest.objects.get(user=self.user).token
        request_id = PasswordResetRequest.objects.get(user=self.user).request_id
        response = self.client.get(
            f"/api/v2/accounts/password/reset_form/?request_id={request_id}&token={reset_token}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["response"]["result"]
        response = self.client.post(
            "/api/v2/accounts/password/reset_form/",
            {"request_id": request_id, "token": reset_token, "password": "super-secret-pAssword2!"},
        )
        assert response.data["response"]["result"]["reset"]
        user = User.objects.get(
            email="standard@gov.uk",  # /PS-IGNORE
        )
        assert user.check_password("super-secret-pAssword2!")
        request_id = PasswordResetRequest.objects.get(user=self.user).request_id
        response = self.client.get(
            f"/api/v2/accounts/password/reset_form/?request_id={request_id}&token={reset_token}"
        )
        assert not response.data["response"]["result"]
        response = self.client.post(
            "/api/v2/accounts/password/reset_form/",
            {"request_id": request_id, "token": reset_token, "password": "super-secret-pAssword3!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "Invalid or expired link"
        user = User.objects.get(
            email="standard@gov.uk",  # /PS-IGNORE
        )
        assert user.check_password("super-secret-pAssword2!")

    def test_reset_password_validates_new_password(self):
        self.client.get(f"/api/v1/accounts/password/request_reset/?email={self.user.email}")
        reset_token = PasswordResetRequest.objects.get(user=self.user).token
        request_id = PasswordResetRequest.objects.get(user=self.user).request_id
        response = self.client.post(
            "/api/v2/accounts/password/reset_form/",
            {"request_id": request_id, "token": reset_token, "password": ""},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error_summaries": ["You need to enter your password"],
            "password": ["Enter your password"],
        }
        response = self.client.post(
            "/api/v2/accounts/password/reset_form/",
            {"request_id": request_id, "token": reset_token, "password": "Sa1!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error_summaries": ["The password is not using the correct format"],
            "password": [
                "Enter a password that contains 8 or more characters, at least one lowercase letter, at least one"
                " capital letter, at least one number and at least one special character for example  !@#$%^&"
            ],
        }
