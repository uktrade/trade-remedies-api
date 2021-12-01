from abc import ABC

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException
from rest_framework import serializers, status
from rest_framework.authtoken.serializers import AuthTokenSerializer

from django_countries.serializers import CountryFieldMixin

from authentication.models.two_factor_auth import TwoFactorAuthLocked
from authentication.models.user import User


class Invalid2FAToken(APIException):
    """Invalid2FAToken.

    Exception raised when a two factor authentication request is invalid.
    """
    status_code = status.HTTP_400_BAD_REQUEST


class TooManyAttempts(APIException):
    """TooManyAttempts.

    Exception raised when in excess of settings.TWO_FACTOR_MAX_ATTEMPTS
    two factor authentication requests have been made.
    """
    status_code = status.HTTP_401_UNAUTHORIZED


class TrustedTokenSerializer(serializers.Serializer):  # noqa
    """Trusted Token Serializer.

    Validates that API clients provide a trusted token.
    """
    trusted_token = serializers.CharField(
        label=_("Trusted Token"),
        write_only=True,
    )

    @staticmethod
    def validate_trusted_token(value):
        error_msg = _("Unable to fulfil request without a valid trusted token.")
        if value != settings.ANON_USER_TOKEN:
            raise serializers.ValidationError(error_msg, code='authorization')
        return value


class TrustedAuthTokenSerializer(AuthTokenSerializer, TrustedTokenSerializer):  # noqa
    """Trusted Auth Token Serializer.

    Uses authentication logic provided `AuthTokenSerializer` and in addition
    validates that API clients provide a trusted token.
    """


class TwoFactorTokenSerializer(TrustedTokenSerializer):  # noqa
    """Two Factor Token Serializer.

    Validates presence and validity of `two_factor_token` in a two-factor
    authentication request.
    """
    two_factor_token = serializers.CharField(
        label=_("Two Factor Token"),
        write_only=True,
    )

    def validate_two_factor_token(self, value):
        request = self.context.get("request")
        user_agent = request.META.get("HTTP_X_USER_AGENT", None)
        try:
            valid = request.user.two_factor.validate_token(value, user_agent)
        except TwoFactorAuthLocked:
            msg = ("Too many two factor authentication attempts "
                   f"(exceeded {settings.TWO_FACTOR_MAX_ATTEMPTS}), "
                   f"account locked for {settings.TWO_FACTOR_LOCK_MINUTES} minutes."
                   )
            raise TooManyAttempts(
                detail=msg, code="too-many-2fa-attempts"
            )
        if valid:
            return value
        raise Invalid2FAToken(
            detail="Two factor token is invalid.",
            code="invalid-2fa-token"
        )


class EmailAvailabilitySerializer(TrustedTokenSerializer):  # noqa
    """Email Availability Serializer."""
    email = serializers.CharField(
        label=_("Email"),
        write_only=True,
    )


class UserSerializer(CountryFieldMixin, serializers.ModelSerializer):
    """User serializer."""
    class Meta:
        model = User
        exclude = ('password', )
