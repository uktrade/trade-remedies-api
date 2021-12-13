"""Authentication Views."""
from django.utils import timezone
from rest_framework import views, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response

from .models.user import User
from .serializers import (
    TrustedTokenSerializer,
    TrustedAuthTokenSerializer,
    EmailAvailabilitySerializer,
    TwoFactorTokenSerializer,
    UserSerializer,
)


class AuthenticationView(ObtainAuthToken):
    """AuthenticationView.

    API Authentication entry point. Any API client that wants authenticated API
    interaction must post `username`, `password` and `trusted_token` (which
    must match `settings.ANON_USER_TOKEN`). The `TrustedAuthTokenSerializer`
    authenticates the request or raises a validation error.

    An authentication token is generated if required. If two factor auth
    is required the token is withheld pending successful 2FA auth, otherwise
    the auth token is returned.
    """
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = TrustedAuthTokenSerializer(data=request.data,
                                                context={'request': request})
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        user = User.objects.get(email=username)
        user_agent = request.META["HTTP_X_USER_AGENT"]
        token, created = Token.objects.get_or_create(user=user)
        if two_factor_required := user.two_factor.required(user_agent):
            user.two_factor.deliver_token(user_agent)
            token_key = "withheld-pending-2fa"
        else:
            token_key = token.key
        return Response(
            {
                "token": token_key,
                "2fa_required": two_factor_required,
            }
        )


class TwoFactorView(views.APIView):
    """TwoFactorView.

    Process two-factor authentication request. Uses `TwoFactorTokenSerializer`
    to check presence and validity of `two_factor_token`.
    """
    authentication_classes = ()

    @staticmethod
    def post(request, *args, **kwargs):
        serializer = TwoFactorTokenSerializer(data=request.data,
                                              context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "token": serializer.validated_data["two_factor_token"],
            }
        )


class TwoFactorResendView(views.APIView):
    """TwoFactorResendView.

    Process request to regenerate and resend a 2FA token. Accessible to
    bearer of `settings.ANON_USER_TOKEN`.
    """
    authentication_classes = ()

    @staticmethod
    def post(request, *args, **kwargs):
        serializer = TrustedTokenSerializer(data=request.data,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_agent = request.META["HTTP_X_USER_AGENT"]
        request.user.two_factor.deliver_token(user_agent)
        return Response(
            {
                "2fa-token-resent": timezone.now(),
            }
        )


class EmailAvailableView(views.APIView):
    """EmailAvailableView.

    Check the availability of an email identity in the system. Accessible to
    bearer of `settings.ANON_USER_TOKEN`.
    """
    authentication_classes = ()

    @staticmethod
    def get(request, *args, **kwargs):
        serializer = EmailAvailabilitySerializer(data=request.data,
                                                 context={'request': request})
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        response = {
            "available": False
        }
        try:
            User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            response["available"] = True
        return Response(response)


class EmailVerifyView(views.APIView):
    """EmailVerifyView.

    When a user is created we create an auth.models.EmailVerification model
    which triggers a 'verify email address' notification. This endpoint
    processes the validation of the code sent.
    """
    # TODO-TRV2 implement me


class UserView(viewsets.ModelViewSet):
    """Users.

    API endpoint for user definitions.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ["get", "head", "post", "patch"]
