from unittest.mock import patch

from rest_framework.test import APITestCase
from cases.tests.test_case import load_system_params
from core.notifier import send_mail, get_context


def get_notify_response(**overrides):
    response = {
        "content": {
            "body": "Test message blah blah",
            "from_email": "trade.remedies.dev@notifications.service.gov.uk",
            "subject": "Test Paul",
        },
        "id": "1a03c4ab-10c2-44ea-9dec-811b3b1c6d20",
        "reference": None,
        "scheduled_for": None,
        "template": {
            "id": "8f486f65-d351-4494-9e79-4b8aadda6fac",
            "uri": "https://api.notifications.service.gov.uk/services/bf/templates/8f",
            "version": 2,
        },
        "uri": "https://api.notifications.service.gov.uk/v2/notifications/1a",
        "to_email": "paul.cooney@digital.trade.gov.uk",
        "template_id": "8f486f65-d351-4494-9e79-4b8aadda6fac",
    }
    response.update(overrides)
    return response


class NotifierTest(APITestCase):
    def setUp(self):
        load_system_params()
        self.context = {"full_name": "Mr Chips"}
        self.email = "test@trade.gov.uk"
        self.template_id = "template-id"

    @patch("core.notifier.NotificationsAPIClient")
    def test_send_mail(self, notifier_client):
        notifier_client().send_email_notification.return_value = get_notify_response()

        report = send_mail(self.email, self.context, self.template_id)

        self.assertEqual(report["to_email"], self.email)
        expected_personalisation = self.context.copy()
        expected_personalisation = get_context(expected_personalisation)
        notifier_client().send_email_notification.assert_called_once_with(
            email_address=self.email,
            template_id=self.template_id,
            personalisation=expected_personalisation,
            reference=None,
        )

    @patch("core.notifier.NotificationsAPIClient")
    def test_send_mail_blocked_by_whitelist(self, notifier_client):
        report = send_mail("x@not_in_whitelist.gov.uk", self.context, self.template_id)

        self.assertFalse(report["whitelist"])
        self.assertEqual(notifier_client().send_email_notification.call_count, 0)

    @patch("core.notifier.NotificationsAPIClient")
    def test_send_mail_override_context(self, notifier_client):
        notifier_client().send_email_notification.return_value = get_notify_response()
        self.context["footer"] = "my footer"

        report = send_mail(self.email, self.context, self.template_id)

        self.assertEqual(report["to_email"], self.email)
        expected_personalisation = self.context.copy()
        expected_personalisation = get_context(expected_personalisation)
        expected_personalisation["footer"] = "my footer"
        notifier_client().send_email_notification.assert_called_once_with(
            email_address=self.email,
            template_id=self.template_id,
            personalisation=expected_personalisation,
            reference=None,
        )
