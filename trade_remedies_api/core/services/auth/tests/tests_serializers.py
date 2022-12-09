from django.conf import settings
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase

from audit import AUDIT_TYPE_LOGIN, AUDIT_TYPE_LOGIN_FAILED
from audit.models import Audit
from config.test_bases import MockRequest, UserSetupTestBase, email, password
from core.models import PasswordResetRequest, SystemParameter, TwoFactorAuth, User
from core.services.auth.serializers import (
    AuthenticationSerializer,
    UserDoesNotExistSerializer,
    UserExistsSerializer,
    PasswordResetRequestSerializer,
    PasswordSerializer,
    RegistrationSerializer,
    TwoFactorAuthRequestSerializer,
    TwoFactorAuthVerifySerializer,
    VerifyEmailSerializer,
)
from organisations.models import Organisation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)


class TestAuthSerializers(TestCase):
    """Test the DRF serializers used in the basic user on-boarding / auth operations."""

    def test_password_serializer_invalid(self):
        """Tests the PasswordSerializer - blank.

        Given that I am on the TRS sign in page

        And I have entered an valid email address

        And I have not entered a password

        When I select the “Sign in” button

        Then I am shown an error message
        """
        serializer = PasswordSerializer(data={"password": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors.error_list)

    def test_password_serializer_valid(self):
        """Tests the PasswordSerializer returns valid when a complex password is used"""
        serializer = PasswordSerializer(data={"password": password})
        self.assertTrue(serializer.is_valid())

    def test_email_serializer_invalid(self):
        """Tests that the UserExistsSerializer raises a validation error when using an email that doesn't belong to a user"""
        serializer = UserExistsSerializer(data={"email": email})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors.error_list)
        self.assertFalse(serializer.user_queryset(email).exists())

    def test_email_serializer_valid(self):
        """Tests that the UserExistsSerializer is valid when using an email that does exist"""
        user = User.objects.create_user(email=email, password=password)
        serializer = UserExistsSerializer(data={"email": email})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["email"], email)

    def test_email_availability_serializer_invalid(self):
        """Tests that the UserDoesNotExistSerializer is invalid when passed an email that does exist in the DB"""
        user = User.objects.create_user(email=email, password=password)
        serializer = UserDoesNotExistSerializer(data={"email": email})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors.error_list)

    def test_email_availability_serializer_valid(self):
        """Tests that the UserDoesNotExistSerializer is valid when passed an email that doesn't exist in the DB"""
        serializer = UserDoesNotExistSerializer(data={"email": email})
        self.assertTrue(serializer.is_valid())

    def test_email_serializer_regex(self):
        """Tests that the UserExistsSerializer fails when passed an invalid email.

        Given that I am on the the TRS sign in page

        And I have entered an email address in an invalid format

        And I have entered a password

        When I select the “Sign in” button

        Then I am shown an error message
        """
        serializer = UserExistsSerializer(data={"email": "asd@@@@gmail.com"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors.error_list)
        self.assertEqual(serializer.errors.error_list["email"], "email_not_valid")

    def test_email_serializer_blank(self):
        """UserExistsSerializer fails when blank email passed.

        Given that I am on the  TRS sign in page

        And I have not entered anything in the email address field

        And I have entered a password

        When I select the “Sign in” button

        Then I am shown an error message
        """
        serializer = UserExistsSerializer(data={"email": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors.error_list)
        self.assertEqual(serializer.errors.error_list["email"], "email_required")


class TestAuthenticationSerializer(UserSetupTestBase):
    """Tests the AuthenticationSerializer class."""

    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        self.valid_mock_request = MockRequest(
            META={"HTTP_X_ORIGIN_ENVIRONMENT": settings.PUBLIC_ENVIRONMENT_KEY}
        )

    def test_authentication_serializer_valid(self):
        """Tests that the AuthenticationSerializer is valid when passed a correct user and password"""
        self.user.userprofile.verify_email()  # verifying their email
        serializer = AuthenticationSerializer(
            data={"email": email, "password": password},
            context={"request": self.valid_mock_request},
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.data["token"], self.user.get_access_token().key)

    def test_authentication_serializer_valid_email_not_verified(self):
        """Tests that the AuthenticationSerializer is valid when passed a correct user and password.

        However, with an unverified email address the needs_verify flag on the response_dict will be True.
        """
        serializer = AuthenticationSerializer(
            data={"email": email, "password": password},
            context={"request": self.valid_mock_request},
        )
        serializer.is_valid()
        self.assertTrue(serializer.data["needs_verify"])

    def test_authentication_serializer_invalid_wrong_password(self):
        """Tests that the AuthenticationSerializer is invalid when passed an incorrect password"""
        serializer = AuthenticationSerializer(data={"email": email, "password": "wrong_password"})
        self.assertFalse(serializer.is_valid())

    def test_authentication_serializer_invalid_deleted_user(self):
        """Tests that the AuthenticationSerializer is invalid when passed a User who has been deleted"""
        self.user.delete()
        serializer = AuthenticationSerializer(data={"email": email, "password": password})
        self.assertFalse(serializer.is_valid())

    def test_authentication_serializer_invalid_wrong_environment(self):
        """Tests that the AuthenticationSerializer is invalid when passed an incorrect HTTP_X_ORIGIN_ENVIRONMENT"""
        invalid_mock_request = self.MockRequest(META={"HTTP_X_ORIGIN_ENVIRONMENT": "12354fs"})
        serializer = AuthenticationSerializer(
            data={
                "email": email,
                "password": password,
            },
            context={"request": invalid_mock_request},
        )
        with self.assertRaises(KeyError):
            # It will raise a KeyError as the invalid environment is not in the ENVIRONMENT_GROUPS dict
            serializer.is_valid()

    def test_authentication_serializer_invalid_no_details(self):
        """Tests that the AuthenticationSerializer is invalid when passed neither a username nor password"""
        serializer = AuthenticationSerializer(data={"email": None, "password": None})
        self.assertFalse(serializer.is_valid())

    def test_login_successful_audit_log_created(self):
        """A successful login should create a related audit log.

        Given that a public user attempts to log in

        When they successfully log-in

        Then a record recording the successful log-in is written to the audit log
        """
        self.assertEqual(
            Audit.objects.filter(type=AUDIT_TYPE_LOGIN, created_by=self.user).count(), 0
        )
        self.user.userprofile.verify_email()  # verifying their email
        serializer = AuthenticationSerializer(
            data={"email": email, "password": password},
            context={"request": self.valid_mock_request},
        )
        serializer.is_valid()
        self.assertEqual(
            Audit.objects.filter(type=AUDIT_TYPE_LOGIN, created_by=self.user).count(), 1
        )

    def test_login_failure_audit_log_created(self):
        """A failed login should create a related audit log.

        Given that a public user attempts to log in

        When they fail to log in

        Then a record recording the unsuccessful log-in is written to the audit log
        """
        self.assertEqual(
            Audit.objects.filter(type=AUDIT_TYPE_LOGIN_FAILED, data__email=self.user.email).count(),
            0,
        )
        self.user.userprofile.verify_email()  # verifying their email
        serializer = AuthenticationSerializer(
            data={"email": email, "password": "incorrect"},
            context={"request": self.valid_mock_request},
        )
        serializer.is_valid()
        self.assertEqual(
            Audit.objects.filter(type=AUDIT_TYPE_LOGIN_FAILED, data__email=self.user.email).count(),
            1,
        )


class TestRegistrationSerializer(TestCase):
    """Tests the AuthenticationSerializer class."""

    def setUp(self) -> None:
        """Simulate the request.data that gets sent to this serializer when a new user registers"""
        self.post_data = {
            "email": email,
            "password": password,
            "name": "Test Name",
            "code": "",
            "case_id": "",
            "phone": "",
            "country": "AF",
            "organisation_name": "test_company",
            "organisation_country": "GB",
            "companies_house_id": "12345",
            "organisation_address": "test company road",
            "vat_number": "",
            "eori_number": "",
            "duns_number": "",
            "organisation_website": "",
        }

    def test_registration_serializer_valid(self):
        """Tests that the serializer is valid and creates a new user when correct details are passed"""
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_THIRD_PARTY_USER)
        Organisation.objects.create(id=settings.SECRETARY_OF_STATE_ORGANISATION_ID)

        serializer = RegistrationSerializer(data=self.post_data)
        self.assertTrue(serializer.is_valid())

        self.assertFalse(User.objects.filter(email=email).exists())
        serializer.save()
        self.assertTrue(User.objects.filter(email=email).exists())

    def test_registration_serializer_invalid_missing_organisation_name(self):
        """Tests that the serializer is invalid when code and case_id are passed but not organisation_name"""
        temp_post_data = self.post_data
        temp_post_data["code"] = "123"
        temp_post_data["case_id"] = "5235"
        temp_post_data["organisation_name"] = ""

        serializer = RegistrationSerializer(data=temp_post_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("organisation_name", serializer.errors)

    def test_registration_serializer_invalid_locked_registration(self):
        """Tests that the serializer is invalid when registrations are locked"""
        registration_lock = SystemParameter.objects.create(
            key="REGISTRATION_SOFT_LOCK",
            data_type="bool",
        )
        registration_lock_key = SystemParameter.objects.create(
            key="REGISTRATION_SOFT_LOCK_KEY",
            data_type="str",
        )
        registration_lock.set_value(True)
        registration_lock.save()
        registration_lock_key.set_value("test")
        registration_lock_key.save()
        serializer = RegistrationSerializer(data=self.post_data)
        self.assertFalse(serializer.is_valid())


class TestTwoFactorAuthSerializers(UserSetupTestBase):
    """Tests the TwoFactorAuthRequestSerializer and TwoFactorAuthVerifySerializer classes."""

    def setUp(self) -> None:
        super().setUp()
        self.user.twofactorauth = TwoFactorAuth(user=self.user)
        self.user.save()
        self.valid_mock_request = MockRequest(META={"HTTP_X_USER_AGENT": "TEST_USER_AGENT"})

    def test_two_factor_auth_request_valid(self):
        """Tests that the TwoFactorAuthRequestSerializer is valid when passed a correct instance and model type"""
        serializer = TwoFactorAuthRequestSerializer(
            instance=self.user.twofactorauth,
            data={"delivery_type": "email"},
            context={"request": self.valid_mock_request},
        )
        self.assertTrue(serializer.is_valid())

    def test_two_factor_auth_request_valid_change_delivery_type(self):
        """Tests that the TwoFactorAuthRequestSerializer is valid and changes the delivery_type to EMAIL if the
        user does now have a phone associated with them.
        """
        self.user.contact.phone = None
        self.user.contact.save()
        serializer = TwoFactorAuthRequestSerializer(
            instance=self.user.twofactorauth,
            data={"delivery_type": "sms"},
            context={"request": self.valid_mock_request},
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["delivery_type"], "email")

    def test_two_factor_auth_request_valid_change_delivery_type_for_invalid_phone_number(self):
        """Tests that the TwoFactorAuthRequestSerializer is valid and changes the delivery_type to EMAIL if the
        user has an invalid phone number associated with them.
        """
        self.user.contact.phone = "+447"
        self.user.contact.save()

        serializer = TwoFactorAuthRequestSerializer(
            instance=self.user.twofactorauth,
            data={"delivery_type": "sms"},
            context={"request": self.valid_mock_request},
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["delivery_type"], "email")

    def test_two_factor_auth_request_invalid(self):
        """Tests that the TwoFactorAuthRequestSerializer is invalid when passed a random delivery_type"""
        serializer = TwoFactorAuthRequestSerializer(
            instance=self.user.twofactorauth,
            data={"delivery_type": "asd"},
            context={"request": self.valid_mock_request},
        )
        self.assertFalse(serializer.is_valid())

    def test_two_factor_auth_verify_valid(self):
        """Tests that the TwoFactorAuthVerifySerializer is valid when passed a correct code"""
        code = self.user.twofactorauth.generate_code()
        serializer = TwoFactorAuthVerifySerializer(
            instance=self.user.twofactorauth,
            data={"code": code},
            context={"request": self.valid_mock_request},
        )
        self.assertTrue(serializer.is_valid())

    def test_two_factor_auth_verify_invalid_wrong_code(self):
        """Tests that the TwoFactorAuthVerifySerializer is invalid when passed an incorrect code"""
        self.user.twofactorauth.generate_code()
        serializer = TwoFactorAuthVerifySerializer(
            instance=self.user.twofactorauth,
            data={"code": "wrong_code"},
            context={"request": self.valid_mock_request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.error_list)
        self.assertEqual(serializer.error_list["code"].error_key, "2fa_code_not_valid")

    def test_two_factor_auth_verify_invalid_locked(self):
        """Tests that the TwoFactorAuthVerifySerializer is valid when the TwoFactorAuth object is locked."""
        code = self.user.twofactorauth.generate_code()
        self.user.twofactorauth.lock()
        serializer = TwoFactorAuthVerifySerializer(
            instance=self.user.twofactorauth,
            data={"code": code},
            context={"request": self.valid_mock_request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.error_list)
        self.assertEqual(serializer.error_list["code"].error_key, "2fa_code_locked")


class TestVerifyEmailSerializer(UserSetupTestBase):
    """Tests the VerifyEmailSerializer class."""

    def test_verify_email_serializer_valid(self):
        """Tests that the VerifyEmailSerializer is valid when passed a correct code"""
        self.user.userprofile.verify_email()
        code = self.user.userprofile.email_verify_code
        serializer = VerifyEmailSerializer(
            data={"code": code}, context={"profile": self.user.userprofile}
        )
        self.assertTrue(serializer.is_valid())

    def test_verify_email_serializer_invalid_wrong_code(self):
        """Tests that the VerifyEmailSerializer is valid when passed an incorrect code"""
        serializer = VerifyEmailSerializer(
            data={"code": "wrong_code"}, context={"profile": self.user.userprofile}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


class TestPasswordResetRequestSerializer(UserSetupTestBase):
    """Tests the PasswordResetRequestSerializer class."""

    def setUp(self) -> None:
        super().setUp()

        # Creating a PasswordResetRequest object for our mock user
        self.password_reset_object, self.send_report = PasswordResetRequest.objects.reset_request(
            self.user.email
        )

    def test_verify_email_serializer_valid(self):
        """Tests that the PasswordResetRequestSerializer is valid when passed a correct token"""
        serializer = PasswordResetRequestSerializer(
            data={"token": self.password_reset_object.token, "user_pk": str(self.user.pk)}
        )
        self.assertTrue(serializer.is_valid())

    def test_verify_email_serializer_invalid_wrong_token(self):
        """Tests that the PasswordResetRequestSerializer is valid when passed an incorrect token"""
        serializer = PasswordResetRequestSerializer(
            data={"token": "wrong_token", "user_pk": str(self.user.pk)}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("token", serializer.errors)
