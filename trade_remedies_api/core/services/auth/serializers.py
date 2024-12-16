import logging
import re

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from audit import AUDIT_TYPE_LOGIN, AUDIT_TYPE_LOGIN_FAILED
from audit.utils import audit_log
from config.serializers import CustomValidationModelSerializer, CustomValidationSerializer
from core.exceptions import CustomValidationError
from core.models import PasswordResetRequest, SystemParameter, TwoFactorAuth, User
from core.services.auth.exceptions import AxesLockedOutException
from core.validation_errors import validation_errors
from security.constants import ENVIRONMENT_GROUPS
from .exceptions import TwoFactorRequestedTooMany

logger = logging.getLogger(__name__)


class EmailSerializer(CustomValidationSerializer):
    """Checks if an email address is valid"""

    email = serializers.CharField(
        label=_("Email"),
        trim_whitespace=True,
        error_messages={"blank": validation_errors["email_required"]},
    )

    def user_queryset(self, email: str) -> QuerySet:
        return User.objects.filter(email=email.lower())

    def validate_email(self, value: str) -> str:
        """Email field validator."""
        email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"  # /PS-IGNORE
        if not re.search(email_regex, value) or not value:
            raise CustomValidationError(error_key="email_not_valid")
        return value.lower()


class PasswordSerializer(CustomValidationSerializer):
    """Checks if a password is valid, i.e. meets the minimum complexity requirements."""

    password = serializers.CharField(
        label=_("Password"),
        trim_whitespace=True,
        write_only=True,
        required=True,
        error_messages={"blank": validation_errors["password_required"]},
    )

    def validate_password(self, value: str) -> str:
        capital_regex = r"[A-Z]"
        lowercase_regex = r"[a-z]"
        number_regex = r"[0-9]"
        special_regex = r"[!\"$%&\'#()*+,\-./:;<=>?\\@[\]^_`{|}~]"
        if (
            not re.search(capital_regex, value)
            or not re.search(lowercase_regex, value)
            or not re.search(number_regex, value)
            or not re.search(special_regex, value)
            or not len(value) >= 8
            or not value
        ):
            raise CustomValidationError(error_key="password_fails_requirements")
        return value


class UserExistsSerializer(EmailSerializer):
    """Checks that an email address belongs to a user who exists in the database."""

    def get_user(self, email: str) -> User:
        """Get User model helper."""
        try:
            user = self.user_queryset(email=email).get()
        except User.DoesNotExist:
            raise CustomValidationError(error_key="wrong_email_password_combination")
        return user

    def validate_email(self, value: str) -> str:
        """Email field validator."""
        value = super().validate_email(value)
        self.user = self.get_user(value)
        return value


class UserDoesNotExistSerializer(EmailSerializer):
    """Similar to UserExistsSerializer, but checks if the email address is available and free to use."""

    def validate_email(self, value):
        value = super().validate(value)
        if self.user_queryset(value).exists():
            raise ValidationError(_("User already exists."), code="user_already_exists")
        return value


class PasswordRequestIdSerializer(CustomValidationSerializer):
    request_id = serializers.UUIDField(required=True)

    def validate_request_id(self, value):
        if not PasswordResetRequest.objects.filter(request_id=value).exists():
            raise ValidationError(_("Request does not exist."), code="request_does_not_exist")
        return value


class AuthenticationSerializer(UserExistsSerializer, PasswordSerializer):  # noqa
    """Authentication Serializer used to log users in.

    Validates the username/password combination exists, the account is not deleted, and the request is coming from
    a recognised environment (public/caseworker) depending on the HTTP_X_ORIGIN_ENVIRONMENT key.

    Also exposes a data() method which can be easily returned as part of an HttpResponse object.
    """

    def validate_password(self, value: str) -> str:
        # we always validate the password as we don't want to show complexity error messages when
        # logging in
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_dict = dict()

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        request = self.context.get("request")

        if email and password:
            try:
                user = authenticate(
                    request=self.context.get("request"), email=email, password=password
                )
            except AxesLockedOutException:
                # The user has been locked out after too many incorrect attempts
                raise CustomValidationError(error_key="login_incorrect_timeout")

            if not user or user.deleted_at:
                audit_log(audit_type=AUDIT_TYPE_LOGIN_FAILED, data={"email": email})
                raise CustomValidationError(error_key="wrong_email_password_combination")

            audit_log(audit_type=AUDIT_TYPE_LOGIN, user=user)
            # ensure the origin of the request is allowed for this user group
            env_key = request.META.get("HTTP_X_ORIGIN_ENVIRONMENT")
            user_group = ENVIRONMENT_GROUPS.get(env_key)
            if user_group and not user.has_groups(groups=user_group):
                logger.error(
                    f"{user.email} does not have access to {user_group}" if env_key else f"env_key not defined while logging {user.email}"
                )
                raise CustomValidationError(error_key="invalid_access")

            email_verified = user.is_tra() or user.userprofile.email_verified_at
            if not email_verified:
                self.response_dict["needs_verify"] = True
            self.response_dict["token"] = str(user.get_access_token())

        else:
            raise AuthenticationFailed(
                _("Email and password are required to log in."), code="authorization"
            )

        attrs["user"] = user
        return attrs

    @property
    def data(self):
        user = self.validated_data["user"]
        # We want to refresh the User object in case we've validated invitations in the meantime
        user.refresh_from_db()
        self.response_dict["user"] = user.to_dict(
            user_agent=self.context["request"].META.get("HTTP_X_USER_AGENT")
        )
        return {"result": self.response_dict}


class RegistrationSerializer(
    UserDoesNotExistSerializer, PasswordSerializer, serializers.ModelSerializer
):
    """Registration serializer used to register new users on the platform.

    Validates if registrations are currently being accepted (marked by the REGISTRATION_SOFT_LOCK system parameter) and
    if they have confirmed they represent the organisation in question.

    Also deals with the creation of this new user using the relevant method (create_user) on the User manager.
    """

    code = serializers.CharField(required=False, allow_blank=True)
    case_id = serializers.CharField(required=False, allow_blank=True)
    confirm_invited_org = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "password", "name", "code", "case_id", "confirm_invited_org"]

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs=attrs)
        password = attrs["password"]
        if SystemParameter.get("REGISTRATION_SOFT_LOCK") and not password.startswith(
            SystemParameter.get("REGISTRATION_SOFT_LOCK_KEY")
        ):
            raise ValidationError(
                _("Registrations are currently locked."), code="registration_locked"
            )

        if attrs.get("code") and attrs.get("case_id") and not attrs.get("confirm_invited_org"):
            raise ValidationError(
                {"organisation_name": _("Organisation name is required.")},
                code="organisation_name_required",
            )

        return attrs

    def save(self, **kwargs):
        if not self.instance:  # This is a new user
            # We need to convert self.initial_data it to a normal dictionary as Django's
            # internal representation of QueryDicts store individual values as lists, regardless
            # of how many elements are in that list:
            # https://www.ianlewis.org/en/querydict-and-update
            initial_data = self.initial_data.dict()
            validated_data = {**initial_data, **self.validated_data, **kwargs}
            new_user = User.objects.create_user(**validated_data)
            new_user.userprofile.verify_email()
            return new_user
        return super().save(**kwargs)


class TwoFactorAuthRequestSerializer(CustomValidationModelSerializer):
    """Checks if a 2fa token can be sent to the recipient, and if so, sends it."""

    class Meta:
        model = TwoFactorAuth
        fields = ["delivery_type"]

    def validate(self, attrs):
        try:
            self.send_report = self.instance.two_factor_auth(
                user_agent=self.context["request"].META.get("HTTP_X_USER_AGENT", "NO_USER_AGENT"),
                delivery_type=attrs["delivery_type"],
            )
            return attrs
        except TwoFactorRequestedTooMany:
            last_requested_seconds_ago = (
                settings.TWO_FACTOR_RESEND_TIMEOUT_SECONDS
                - (timezone.now() - self.instance.generated_at).seconds
            )
            if last_requested_seconds_ago == 0:
                last_requested_seconds_ago = 1  # 0 looks quite unattractive so we show 1 instead
            raise CustomValidationError(
                field=validation_errors["2fa_requested_too_many_times"]["field"],
                error_summary=validation_errors["2fa_requested_too_many_times"]["error_summary"]
                % last_requested_seconds_ago,
            )
        except Exception:
            if attrs["delivery_type"] == "sms":
                # Often times the SMS can fail if it's the first option, retry with email
                # We first need to reset the last generated_at attribute, so it doesn't throw an exc
                self.instance.generated_at = None
                self.instance.save()
                return self.validate(attrs={"delivery_type": "email"})
            raise CustomValidationError(error_key="2fa_code_failed_delivery")

    def validate_delivery_type(self, value):
        value = value or TwoFactorAuth.SMS
        if value not in dict(TwoFactorAuth.DELIVERY_TYPE_CHOICES):
            raise ValidationError(_("Invalid 2FA delivery type requested"))
        if value == TwoFactorAuth.SMS and not self.instance.user.phone:
            value = TwoFactorAuth.EMAIL
        return value

    @property
    def data(self):
        self.send_report["delivery_type"] = self.validated_data["delivery_type"]
        return {"result": self.send_report}


class TwoFactorAuthVerifySerializer(CustomValidationModelSerializer):
    """Checks if a given 2fa code is valid.

    Used in POST requests to confirm that the token provided by the user is correct and
    whether or not they should be allowed to log in.
    """

    class Meta:
        model = TwoFactorAuth
        fields = ["code"]

    def validate(self, attrs):
        if not self.instance.code_within_valid_timeframe:
            raise CustomValidationError(error_key="2fa_code_expired")

        return attrs

    def validate_code(self, code):
        if not code:
            raise CustomValidationError(error_key="2fa_code_required")

        if self.instance.is_locked():
            raise CustomValidationError(error_key="2fa_code_locked")

        if self.instance.validate(code):
            # The code is valid!
            self.instance.success(
                user_agent=self.context["request"].META.get("HTTP_X_USER_AGENT", "NO_USER_AGENT")
            )
            return code
        else:
            # The code is invalid!
            self.instance.fail()
            if self.instance.is_locked():
                # The code has been incorrectly entered too many times, it is now locked
                raise CustomValidationError(error_key="2fa_code_locked")
            else:
                # The code was incorrect but the account is still not locked
                raise CustomValidationError(error_key="2fa_code_not_valid", field="code")

    @property
    def data(self):
        return {"result": self.instance.user.to_dict()}


class VerifyEmailSerializer(serializers.Serializer):
    """Checks if a given email verification code is valid."""

    code = serializers.CharField()

    def validate_code(self, value):
        profile = self.context["profile"]
        if value == profile.email_verify_code:
            return value
        raise ValidationError(
            {"code": _("Invalid verification code")}, code="invalid_email_verification_code"
        )


class PasswordResetRequestSerializerV2(serializers.Serializer):
    """Checks if a given password reset token is valid against a given reset request id"""

    token = serializers.CharField()
    request_id = serializers.UUIDField()

    def validate(self, attrs):
        token = attrs["token"]
        request_id = attrs["request_id"]

        if PasswordResetRequest.objects.validate_token_using_request_id(
            token, request_id, validate_only=True
        ):
            return attrs
        raise ValidationError(
            {"token": _("Password reset link invalid")}, code="password_reset_link_invalid"
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Checks if a given password reset token is valid against a given user_pk."""

    token = serializers.CharField()
    user_pk = serializers.CharField()

    def validate(self, attrs):
        token = attrs["token"]
        user_pk = attrs["user_pk"]
        pass

        if PasswordResetRequest.objects.validate_token(token, user_pk, validate_only=True):
            return attrs
        raise ValidationError(
            {"token": _("Password reset link invalid")}, code="password_reset_link_invalid"
        )
