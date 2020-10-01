import datetime
from django.test import TestCase
from django.contrib.auth.models import Group
from django.utils import timezone
from core.models import User, PasswordResetRequest
from unittest.mock import patch, Mock
from django.conf import settings


PASSWORD = "A7Hhfa!jfaw@f"


notify_response = {
    "id": "740e5834-3a29-46b4-9a6f-16142fde533a",
    "reference": "STRING",
    "content": {"body": "MESSAGE TEXT", "from_number": "SENDER"},
    "uri": (
        "https://api.notifications.service.gov.uk/v2/notifications/"
        "740e5834-3a29-46b4-9a6f-16142fde533a"
    ),
    "template": {
        "id": "f33517ff-2a88-4f6e-b855-c550268ce08a",
        "version": 1,
        "uri": (
            "https://api.notifications.service.gov.uk/v2/template/"
            "ceb50d92-100d-4b8b-b559-14fa3b091cd"
        ),
    },
}


class PasswordResetTest(TestCase):
    """
    Tests Password reset
    """

    def setUp(self):
        Group.objects.create(name="Organisation Owner")
        self.user = User.objects.create(email="harel@harelmalka.com", name="Joe Public")
        self.user.set_password(PASSWORD)
        self.user.save()

    @patch("core.models.PasswordResetRequest.send_reset_link")
    def test_reset_request(self, reset_mail):
        reset_mail.return_value = notify_response
        reset, send_report = PasswordResetRequest.objects.reset_request(self.user.email)
        assert type(reset) is PasswordResetRequest
        assert bool(reset.code)
        assert reset.age_days == 0

    def test_reset_age(self):
        reset_valid = PasswordResetRequest.objects.create(
            user=self.user,
            created_at=timezone.now()
            - datetime.timedelta(hours=settings.PASSWORD_RESET_CODE_AGE_HOURS),
        )
        reset_valid.generate_code()
        reset_invalid = PasswordResetRequest.objects.create(
            user=self.user,
            created_at=timezone.now()
            - datetime.timedelta(hours=settings.PASSWORD_RESET_CODE_AGE_HOURS + 1),
        )
        code_valid = PasswordResetRequest.objects.validate_code(
            f"{self.user.id}!{reset_valid.code}", validate_only=True
        )
        code_invalid = PasswordResetRequest.objects.validate_code(
            f"{self.user.id}!{reset_invalid.code}", validate_only=True
        )
        assert code_valid
        assert code_invalid

    @patch("core.models.PasswordResetRequest.send_reset_link")
    def test_reset_pass(self, reset_mail):
        reset_mail.return_value = notify_response
        reset, send_report = PasswordResetRequest.objects.reset_request(self.user.email)
        code = f"{reset.user.id}!{reset.code}"
        reset_user = PasswordResetRequest.objects.password_reset(code, "New!Passw0rd")
        reset_user_again = PasswordResetRequest.objects.password_reset(code, "New!Passw0rd")
        assert type(reset_user) == User
        assert self.user == reset_user
        assert reset_user_again is None
