from django.utils import timezone
from rest_framework import views, viewsets, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from authentication.models.user import User
from authentication.serializers import (
    UsernameSerializer,
    TrustedAuthTokenSerializer,
    TwoFactorTokenSerializer,
    UserSerializer,
    EmailVerificationSerializer,
)


class PasswordResetView(views.APIView):
    """Password reset view.

    When a user is created we create an auth.models.EmailVerification model
    which triggers a 'verify email address' notification. This endpoint
    processes the validation of the code sent.
    """

    @staticmethod
    def post(request, *args, **kwargs):
        serializer = EmailVerificationSerializer(data=kwargs,
                                                 context={'request': request})
        serializer.is_valid(raise_exception=True)
        response = {
            "verified": True
        }
        return Response(response)
