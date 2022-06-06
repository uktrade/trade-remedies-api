from rest_framework.test import APITransactionTestCase
from rest_framework import status


class PasswordResetTest(APITransactionTestCase):
    def test_user_access_allowed(self):
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        response = self.client.get(f"/api/v1/cases/{self.case.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
