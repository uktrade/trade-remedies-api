import datetime

from django.contrib.auth.models import Group
from django.test import TestCase

from core.models import PasswordResetRequest, User

PASSWORD = "A7Hhfa!jfaw@f"


class PasswordResetTest(TestCase):
    """
    Tests Password reset
    """

    def setUp(self):
        Group.objects.create(name="Organisation Owner")
        self.user = User.objects.create(email="harel@harelmalka.com", name="Joe Public")  # /PS-IGNORE
        self.user.set_password(PASSWORD)
        self.user.save()

    def test_reset_request(self):
        reset, send_report = PasswordResetRequest.objects.reset_request(self.user.email)
        assert type(reset) is PasswordResetRequest
        assert bool(reset.token)  # Checking that the method actually generates and attaches a token to the object

    def test_reset_is_valid(self):
        reset_valid = PasswordResetRequest.objects.create(user=self.user)
        token = reset_valid.generate_token()

        self.assertTrue(
            PasswordResetRequest.objects.validate_token(
                token=token,
                user_pk=self.user.pk,
                validate_only=True
            )
        )

    def test_reset_is_invalid_because_of_wrong_token(self):
        reset = PasswordResetRequest.objects.create(user=self.user)
        token = reset.generate_token()

        self.assertFalse(
            PasswordResetRequest.objects.validate_token(
                token='123das',
                user_pk=self.user.pk,
                validate_only=True
            )
        )

    def test_reset_request_invalidates_existing_tokens(self):
        reset = PasswordResetRequest.objects.create(user=self.user)
        reset.generate_token()

        self.assertTrue(reset.invalidated_at is None)
        self.assertTrue(reset.ack_at is None)

        PasswordResetRequest.objects.reset_request(self.user.email)
        reset.refresh_from_db()

        self.assertEqual(reset.invalidated_at.date(), datetime.date.today())

    def test_password_reset_works(self):
        reset = PasswordResetRequest.objects.create(user=self.user)
        token = reset.generate_token()
        new_password = 'New!Passw0rd'

        # First we check if the password_reset method actually changes the password and returns the User object
        reset_user = PasswordResetRequest.objects.password_reset(token, self.user.pk, new_password)
        self.assertEqual(self.user, reset_user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

        new_password = 'New!PASDD123!'
        # Now we try the password reset again, as the token is invalid it should return None and not change the password
        reset_user = PasswordResetRequest.objects.password_reset(token, self.user.pk, new_password)
        self.assertEqual(reset_user, None)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(new_password))
