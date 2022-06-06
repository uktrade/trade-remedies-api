from rest_framework.test import APITransactionTestCase
from rest_framework import status


class PasswordResetTest(APITransactionTestCase):
    def test_requests_password_reset(self):
        self.client.force_authenticate()
        response = self.client.get("/api/v2/accounts/password/request_reset/")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_requests_password_reset_via_request_id(self):
        self.client.force_authenticate()
        response = self.client.get("/api/v2/accounts/password/request_reset/")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_resets_password(self):
        self.client.force_authenticate()
        response = self.client.get("/api/v2/accounts/password/reset_form/")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
