from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.healthcheck import application_service_health


class HealthCheckTestCase(SimpleTestCase):
    # we need to mock the celery app as it will fail otherwise and the overall healthcheck will fail
    @patch.object(settings, "REDIS_BASE_URL", "redis://redis:6379")
    @patch.object(settings, "REDIS_DATABASE_NUMBER", 0)
    @patch.object(settings, "OPENSEARCH_URI", "http://opensearch.com")
    @patch(
        "config.celery.app.control.inspect",
        return_value=Mock(attrs={"ping": Mock(return_value=True)}),
    )
    @patch(
        "django.db.connection.ensure_connection",
        return_value=True,
    )
    def test_application_issue(self, mocked_celery_app, mocked_ensure_connection):
        # Test when the Redis service is up and running
        with patch("redis.StrictRedis.from_url") as mock_from_url:
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            xml = application_service_health()
            mock_redis.ping.assert_called_once()
            self.assertIn("OK", xml)

    @patch.object(settings, "REDIS_BASE_URL", "redis://redis:6379")
    @patch.object(settings, "REDIS_DATABASE_NUMBER", 0)
    @patch.object(settings, "OPENSEARCH_URI", "http://opensearch.com")
    @patch(
        "config.celery.app.control.inspect",
        return_value=Mock(attrs={"ping": Mock(return_value=True)}),
    )
    @patch(
        "django.db.connection.ensure_connection",
        return_value=True,
    )
    def test_application_issue_error(self, mocked_celery_app, mocked_ensure_connection):
        # Test when there is an issue in the redis service
        with patch("redis.StrictRedis.from_url") as mock_from_url:
            mock_redis = Mock()
            mock_redis.ping.side_effect = Exception("Redis connection failed")
            mock_from_url.return_value = mock_redis
            xml = application_service_health()
            mock_redis.ping.assert_called_once()
            self.assertIn("Error", xml)

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
