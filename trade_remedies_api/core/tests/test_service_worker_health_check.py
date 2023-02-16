from unittest.mock import patch
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.healthcheck import application_service_health


class HealthCheckTestCase(SimpleTestCase):
    @patch.object(settings, "REDIS_BASE_URL", "http://redis")
    @patch.object(settings, "REDIS_DATABASE_NUMBER", 0)
    @patch.object(settings, "OPENSEARCH_URI", "http://opensearch.com")
    @patch("redis.Redis.ping")
    def test_application_issue(self, mock_redis_ping):
        html = application_service_health()
        mock_redis_ping.assert_called_once()
        self.assertIn("OK", html)

    @patch.object(settings, "REDIS_BASE_URL", "http://redis")
    @patch.object(settings, "REDIS_DATABASE_NUMBER", 0)
    @patch.object(settings, "OPENSEARCH_URI", "http://opensearch.com")
    @patch("redis.Redis.ping", side_effect=Exception("Redis connection failed"))
    def test_application_issue_error(self, mock_redis_ping):
        html = application_service_health()
        mock_redis_ping.assert_called_once()
        self.assertIn("Error", html)

    @patch(
        "core.views.application_service_health",
        return_value="<status><strong>OK</strong></status>",
    )
    def test_health_check(self, _mock_application_service_health):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OK", response.content)
        self.assertEqual(response["content-type"], "text/xml")

    @patch(
        "core.views.application_service_health",
        return_value="<status><strong>Error</strong></status>",
    )
    def test_health_check_error(self, _mock_application_service_health):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Error", response.content)
        self.assertEqual(response["content-type"], "text/xml")
