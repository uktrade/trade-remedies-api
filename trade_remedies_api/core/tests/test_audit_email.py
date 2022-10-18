import smtplib
import uuid

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from notifications_python_client.errors import HTTPError

from core.models import SystemParameter
from core.notifier import get_client
from core.tasks import check_email_delivered

MOCK_AUDIT_EMAIL_TO_ADDRESS = "test@example.com"  # /PS-IGNORE


class TestAuditEmail(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("load_sysparams")  # Load system parameters
        call_command("notify_env")  # Load the template IDs from GOV.NOTIFY

    @override_settings(GOV_NOTIFY_API_KEY=settings.GOV_NOTIFY_TESTING_KEY)
    def setUp(self) -> None:
        self.notify = get_client()
        self.personalisation = {"code": "test_code", "footer": "test footer"}
        self.template_id = SystemParameter.get("PUBLIC_2FA_CODE_EMAIL")
        self.send_report = self.notify.send_email_notification(
            email_address=MOCK_AUDIT_EMAIL_TO_ADDRESS,
            template_id=self.template_id,
            personalisation=self.personalisation,
            reference=f"TEST-{uuid.uuid4()}",
        )

    def test_smtp_connection(self):
        """Testing that the smtp connection can be made"""
        server = smtplib.SMTP(settings.AUDIT_EMAIL_SMTP_HOST, settings.AUDIT_EMAIL_SMTP_PORT)
        server.starttls()
        server.login(settings.AUDIT_EMAIL_SMTP_USERNAME, settings.AUDIT_EMAIL_SMTP_PASSWORD)

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_audit_email_sent(self):
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        self.assertEqual(sent_mail, {})  # An empty return dict means all mail was accepted

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_audit_email_sent(self):
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        subject = msg.get("subject")
        self.assertIn("Delivered", subject)
        self.assertIn(MOCK_AUDIT_EMAIL_TO_ADDRESS, subject)

    def test_missing_email(self):
        with self.assertRaises(HTTPError) as e:
            check_email_delivered(delivery_id=uuid.uuid4(), context=self.personalisation)
        self.assertEqual(e.exception.status_code, 404)

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_missing_footer(self):
        """Tests that the missing footer parameter is inserted into the email"""
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context={"code": "test_code"}
        )
        body = str(msg)
        self.assertIn("Department for International Trade", body)
        self.assertIn("Investigations Team", body)

    def test_correct_footer(self):
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        body = str(msg)
        self.assertIn("test footer", body)

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_to_address(self):
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        to_address = msg.get("to")
        self.assertEqual(to_address, MOCK_AUDIT_EMAIL_TO_ADDRESS)

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_from_address(self):
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        from_address = msg.get("from")
        self.assertIn(settings.AUDIT_EMAIL_FROM_ADDRESS, from_address)
        self.assertIn(settings.AUDIT_EMAIL_FROM_NAME, from_address)

    @override_settings(AUDIT_EMAIL_TO_ADDRESS=MOCK_AUDIT_EMAIL_TO_ADDRESS)
    def test_correct_email(self):
        """Tests that the correct HTML email is inserted into the audit email"""
        sent_mail, msg = check_email_delivered(
            delivery_id=self.send_report["id"], context=self.personalisation
        )
        body = str(msg)
        self.assertIn("test_code", body)
