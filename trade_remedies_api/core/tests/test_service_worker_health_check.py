from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse


class HealthCheckTestCase(TestCase):
    @patch("core.views.application_issue", return_value=None)
    def test_health_check(self, _mock_application_issue):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response.content, "OK")

    @patch("core.views.application_issue", return_value="__Sample_Error_Message__")
    def test_health_check_error(self, _mock_application_issue):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response.content, "Error")
