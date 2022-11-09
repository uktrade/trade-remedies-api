import datetime
import uuid
from unittest.mock import patch

from celery.exceptions import Retry
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import SystemParameter
from core.notifier import get_client, notify_footer
from core.tasks import check_email_delivered

MOCK_AUDIT_EMAIL_TO_ADDRESS = "test@example.com"  # /PS-IGNORE

# use pytest patch to mock a working and failing smtp server
# instead of email being sent through mail system, it mocks it so we don't have to wait
# maybe make smtp lib a variable that can either be a mock or the real
# LITE has integration tests that run after deployment

random_uuid = str(uuid.uuid4())


def fake_get_notification_by_id():
    return {
        "id": random_uuid,
        "subject": "Sign-in authentication code for Trade Remedies Service",
        "status": "delivered",
        "email_address": MOCK_AUDIT_EMAIL_TO_ADDRESS,
        "template": {"id": random_uuid},
    }


def fake_post_template_preview():
    return {
        "id": random_uuid,
        "body": f"{notify_footer()} - test_code",
        "html": f"<p>{notify_footer()} - test_code</p>",
    }


@override_settings(
    AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS,
    GOV_NOTIFY_API_KEY=settings.GOV_NOTIFY_TESTING_KEY,
)
@patch("notifications_python_client.NotificationsAPIClient.post_template_preview")
@patch("notifications_python_client.NotificationsAPIClient.get_notification_by_id")
@patch("smtplib.SMTP")
class TestAuditEmail(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("load_sysparams")  # Load system parameters
        call_command("notify_env")  # Load the template IDs from GOV.NOTIFY
        cls.personalisation = {"code": "test_code", "footer": "test footer"}
        cls.template_id = SystemParameter.get("PUBLIC_2FA_CODE_EMAIL")

        with patch(
            "notifications_python_client.NotificationsAPIClient.send_email_notification",
            return_value={"id": random_uuid},
        ):
            cls.notify = get_client()
            cls.send_report = cls.notify.send_email_notification(
                email_address=MOCK_AUDIT_EMAIL_TO_ADDRESS,
                template_id=cls.template_id,
                personalisation=cls.personalisation,
                reference=f"TEST-{uuid.uuid4()}",
            )

    def test_audit_email_correct_subject(self, smtp, get_notification_by_id, post_template_preview):
        get_notification_by_id.return_value = fake_get_notification_by_id()
        post_template_preview.return_value = fake_post_template_preview()
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        subject = msg.get("subject")
        self.assertIn("Delivered", subject)
        self.assertIn(MOCK_AUDIT_EMAIL_TO_ADDRESS, subject)

    def test_correct_footer(self, smtp, get_notification_by_id, post_template_preview):
        get_notification_by_id.return_value = fake_get_notification_by_id()
        post_template_preview.return_value = {
            "id": random_uuid,
            "body": f"{notify_footer()} - test footer",
            "html": f"<p>{notify_footer()} - test footer</p>",
        }
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        body = str(msg)
        self.assertIn("test footer", body)

    def test_to_address(self, smtp, get_notification_by_id, post_template_preview):
        get_notification_by_id.return_value = fake_get_notification_by_id()
        post_template_preview.return_value = fake_post_template_preview()
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        to_address = msg.get("to")
        self.assertEqual(to_address, MOCK_AUDIT_EMAIL_TO_ADDRESS)

    def test_from_address(self, smtp, get_notification_by_id, post_template_preview):
        get_notification_by_id.return_value = fake_get_notification_by_id()
        post_template_preview.return_value = fake_post_template_preview()
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        from_address = msg.get("from")
        self.assertIn(settings.AUDIT_EMAIL_FROM_ADDRESS, from_address)
        self.assertIn(settings.AUDIT_EMAIL_FROM_NAME, from_address)

    def test_correct_email(self, smtp, get_notification_by_id, post_template_preview):
        get_notification_by_id.return_value = fake_get_notification_by_id()
        post_template_preview.return_value = fake_post_template_preview()
        """Tests that the correct HTML email is inserted into the audit email"""
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        body = str(msg)
        self.assertIn("test_code", body)

    def test_retry(self, smtp, get_notification_by_id, post_template_preview):
        return_get_value = fake_get_notification_by_id()
        return_get_value.update(
            {
                "status": "sending",
                "created_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
        )
        get_notification_by_id.return_value = return_get_value
        post_template_preview.return_value = fake_post_template_preview()
        failed_send_report = self.notify.send_email_notification(
            email_address="temp-fail@simulator.notify",  # /PS-IGNORE
            template_id=self.template_id,
            personalisation=self.personalisation,
            reference=f"TEMP-FAIL-TEST-{uuid.uuid4()}",
        )
        with self.assertRaises(Retry):
            check_email_delivered(
                delivery_id=failed_send_report["id"],
                context=self.personalisation,
            )

    def test_hyphenated_status(self, smtp, get_notification_by_id, post_template_preview):
        return_get_value = fake_get_notification_by_id()
        return_get_value.update({"status": "permanent-failure"})
        get_notification_by_id.return_value = return_get_value
        post_template_preview.return_value = fake_post_template_preview()
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        subject = msg.get("subject")
        self.assertIn("Permanent failure", subject)
        self.assertIn(MOCK_AUDIT_EMAIL_TO_ADDRESS, subject)
