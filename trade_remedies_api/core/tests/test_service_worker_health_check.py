from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse

from core.notifier import application_service_health


class HealthCheckTestCase(SimpleTestCase):
    # def test_application_issue(self):
    #     result = application_service_health()
    #     status, avg_response_time = result
    #     self.assertEqual(status, "OK")
    #     self.assertGreater(avg_response_time, 0)

    @patch(
        "core.views.application_service_health",
        return_value="<status><strong>OK</strong></status>",
    )
    def test_health_check(self, _mock_application_issue):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OK", response.content)
        self.assertEqual(response["content-type"], "text/xml")

    @patch(
        "core.views.application_service_health",
        return_value="<status><strong>Error</strong></status>",
    )
    def test_health_check_error(self, _mock_application_issue):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Error", response.content)
        self.assertEqual(response["content-type"], "text/xml")
