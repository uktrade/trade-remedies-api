import logging

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from config.version import __version__
from core.models import PasswordResetRequest, SystemParameter, TwoFactorAuth, User
from core.services.exceptions import AccessDenied
from security.constants import ENVIRONMENT_GROUPS

logger = logging.getLogger(__name__)


class PasswordSerializer(serializers.Serializer):
    """Checks if a password is valid, i.e. meets the minimum complexity requirements."""
    password = serializers.CharField(label=_("Password"), trim_whitespace=True, write_only=True, required=True)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise ValidationError(detail="<br/>".join(exc.messages), code="password_not_complex")
        return value


class EmailSerializer(serializers.Serializer):
    """Checks that an email address belongs to a user who exists in the database."""
    email = serializers.CharField(label=_("Email"), write_only=True, trim_whitespace=True, required=True)

    def user_queryset(self, email: str) -> QuerySet:
        return User.objects.filter(email=email.lower())

    def get_user(self, email: str) -> User:
        """Get User model helper."""
        try:
            user = self.user_queryset(email=email).get()
        except User.DoesNotExist:
            raise ValidationError(_("User does not exist."), code="user_does_not_exist")
        return user

    def validate_email(self, value: str) -> str:
        """Email field validator."""
        self.get_user(value)
        return value


class EmailAvailabilitySerializer(EmailSerializer):
    """Similar to EmailSerializer, but checks if the email address is available and free to use."""
    def validate_email(self, value):
        if self.user_queryset(value).exists():
            raise ValidationError(_("User already exists."), code="user_already_exists")
        return value


class AuthenticationSerializer(EmailSerializer, PasswordSerializer):  # noqa
    """Authentication Serializer used to log users in.

    Validates the username/password combination exists, the account is not deleted, and the request is coming from
    a recognised environment (public/caseworker) depending on the HTTP_X_ORIGIN_ENVIRONMENT key.

    Also exposes a data() method which can be easily returned as part of an HttpResponse object.
    """
    response_dict = {
        "version": __version__
    }

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        request = self.context.get("request")

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )

            if not user or user.deleted_at:
                raise AccessDenied(_(
                    "You have entered an incorrect email address or password. "
                    "Please try again or click on the Forgotten password link below."
                ), code='authorization')

            # ensure the origin of the request is allowed for this user group
            env_key = request.META.get("HTTP_X_ORIGIN_ENVIRONMENT")
            if not self.context.get("request") or not user.has_groups(groups=ENVIRONMENT_GROUPS[env_key]):
                if not env_key:
                    logger.error(f"env_key not defined while logging {user.email}")
                else:
                    logger.error(
                        f"env_key = {env_key};"
                        f"{user.email} does not have access to {ENVIRONMENT_GROUPS[env_key]}"
                    )
                raise AccessDenied(_("Invalid access to environment"))

            email_verified = user.is_tra() or not user.userprofile.email_verified_at
            if not email_verified:
                self.response_dict["needs_verify"] = True
            self.response_dict["token"] = str(user.get_access_token())

        else:
            raise AccessDenied(_("Email and password are required to log in."), code='authorization')

        attrs['user'] = user
        return attrs

    @property
    def data(self):
        user = self.validated_data["user"]
        user.refresh_from_db()  # We want to refresh the User object in case we've validated invitations in the meantime
        self.response_dict["user"] = user.to_dict(user_agent=self.context["request"].META.get("HTTP_X_USER_AGENT"))
        return self.response_dict


class RegistrationSerializer(EmailAvailabilitySerializer, PasswordSerializer, serializers.ModelSerializer):
    """Registration serializer used to register new users on the platform.

    Validates if registrations are currently being accepted (marked by the REGISTRATION_SOFT_LOCK system parameter) and
    if they have confirmed they represent the organisation in question.

    Also deals with the creation of this new user using the relevant method (create_user) on the User manager.
    """
    code = serializers.CharField(required=False)
    case_id = serializers.CharField(required=False)
    confirm_invited_org = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ["email", "password", "name", "code", "case_id", "confirm_invited_org"]

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs=attrs)
        password = attrs["password"]
        if SystemParameter.get("REGISTRATION_SOFT_LOCK") and not password.startswith(
                SystemParameter.get("REGISTRATION_SOFT_LOCK_KEY")
        ):
            raise ValidationError(_("Registrations are currently locked."), code='registration_locked')

        if attrs.get("code") and attrs.get("case_id") and not attrs.get("confirm_invited_org"):
            raise ValidationError(_("Organisation name is required."), code="organisation_name_required")

        return attrs

    def save(self, **kwargs):
        if not self.instance:  # This is a new user
            # We need the initial_data as it contains the POST data used to create the User, e.g. organisation_name
            # It gets overridden by the validated_data
            validated_data = {**self.initial_data, **self.validated_data, **kwargs}
            # Very very strange, unpacking the initial_data dictionary turns strings into lists, need to revert
            new_validated_data = {}
            for key, value in validated_data.items():
                if isinstance(value, list):
                    new_validated_data[key] = value[0]
                else:
                    new_validated_data[key] = value
            new_user = User.objects.create_user(**new_validated_data)
            new_user.userprofile.verify_email()
            return new_user
        return super().save(**kwargs)


class TwoFactorAuthSerializer(EmailSerializer, serializers.ModelSerializer):
    """Checks if a given 2fa code is valid.

    Used in POST requests to confirm that the token provided by the user is correct and whether or not they should be
    allowed to log in.
    """
    class Meta:
        model = TwoFactorAuth
        fields = ["delivery_type", "code"]

    def validate(self, attrs):
        if self.instance.is_locked():
            raise ValidationError(_(
                "You have entered an incorrect code too many times "
                "and we have temporarily locked your account.",
                code="2fa_lockout"
            ))
        if self.instance.validate(attrs["code"]):
            self.instance.success(user_agent=self.context["request"].META["HTTP_X_USER_AGENT"])
            return attrs
        else:
            self.instance.fail()
            raise ValidationError(_("Invalid code"), code="invalid_2fa_code")


class VerifyEmailSerializer(serializers.Serializer):
    """Checks if a given email verification code is valid."""
    code = serializers.CharField()

    def validate_code(self, value):
        profile = self.context["profile"]
        if value == profile.email_verify_code:
            return value
        raise ValidationError(_("Invalid verification code"), code="invalid_email_verification_code")


class PasswordResetSerializer(serializers.Serializer):
    """Checks if a given password reset token is valid against a given user_pk."""
    token = serializers.CharField()
    user_pk = serializers.CharField()

    def validate(self, attrs):
        token = attrs["token"]
        user_pk = attrs["user_pk"]

        if PasswordResetRequest.objects.validate_token(token, user_pk, validate_only=True):
            return attrs
        raise ValidationError(_("Password reset link invalid"), code="password_reset_link_invalid")

