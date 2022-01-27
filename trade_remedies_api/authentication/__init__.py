"""Authentication App."""
import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
import rest_framework.exceptions as auth_exceptions


default_app_config = "authentication.apps.AuthenticationConfig"


class ExpiringTokenAuthentication(TokenAuthentication):
    """ExpiringTokenAuthentication.

    Custom Token Authentication class that ensures we raise AuthenticationFailed
    if a token is too old.
    """
    def authenticate_credentials(self, key: str) -> tuple:
        """authenticate_credentials override."""
        from rest_framework.authtoken.models import Token
        user, token = super().authenticate_credentials(key)
        max_age = datetime.timedelta(minutes=settings.AUTH_TOKEN_MAX_AGE_MINUTES)
        if token.created < timezone.now() - max_age:
            token.delete()
            Token.objects.create(user=token.user)
            raise auth_exceptions.AuthenticationFailed('Auth token has expired')
        return user, token
