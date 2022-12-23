from unittest.mock import patch

from rest_framework.test import APITestCase
from cases.tests.test_case import load_system_params
from core.notifier import send_mail, get_context, send_sms


def get_notify_response(**overrides):
    response = {
        "content": {
            "body": "Test message blah blah",
            "from_email": "trade.remedies.dev@notifications.service.gov.uk",  # /PS-IGNORE
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
        "to_email": "paul.cooney@digital.trade.gov.uk",  # /PS-IGNORE
        "template_id": "8f486f65-d351-4494-9e79-4b8aadda6fac",
    }
    response.update(overrides)
    return response


def get_notify_sms_response(**overrides):
    response = {
        "id": "740e5834-3a29-46b4-9a6f-16142fde533a",
        "reference": "STRING",
        "content": {"body": "MESSAGE TEXT", "from_number": "+447123456789"},
        "uri": "https://api.notifications.service.gov.uk/v2/notifications/740e5834-3a29-46b4-9a6f-16142fde533a",
        "template": {
            "id": "f33517ff-2a88-4f6e-b855-c550268ce08a",
            "version": 1,
            "uri": "https://api.notifications.service.gov.uk/v2/template/ceb50d92-100d-4b8b-b559-14fa3b091cd",  # /PS-IGNORE
        },
    }

    response.update(overrides)
    return response


class NotifierTest(APITestCase):
    def setUp(self):
        load_system_params()
        self.context = {"full_name": "Mr Chips"}
        self.email = "test@trade.gov.uk"  # /PS-IGNORE
        self.template_id = "template-id"
        self.phone_number = "+447987654321"

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
    def test_send_sms(self, notifier_client):
        notifier_client().send_sms_notification.return_value = get_notify_sms_response()

        report = send_sms(self.phone_number, self.context, self.template_id)

        self.assertEqual(report["content"]["from_number"], "+447123456789")
        notifier_client().send_sms_notification.assert_called_once_with(
            phone_number=self.phone_number,
            template_id=self.template_id,
            personalisation=self.context,
            reference=None,
        )

    def test_send_mail_blocked_by_whitelist(self):
        report = send_mail("x@not_in_whitelist.dev", self.context, self.template_id)

        self.assertFalse(report["whitelist"])

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
