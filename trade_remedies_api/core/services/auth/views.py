import logging

from axes.utils import reset
from django.contrib.auth import login
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from flags.state import flag_enabled
from rest_framework import status
from rest_framework.views import APIView

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from core.models import PasswordResetRequest, SystemParameter, TwoFactorAuth, UserProfile, User
from core.notifier import send_mail
from core.services.base import ResponseError, ResponseSuccess, TradeRemediesApiView
from core.services.exceptions import InvalidRequestParams
from invitations.models import Invitation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)

from audit import AUDIT_TYPE_PASSWORD_RESET, AUDIT_TYPE_PASSWORD_RESET_FAILED
from audit.utils import audit_log
from .serializers import (
    AuthenticationSerializer,
    UserDoesNotExistSerializer,
    PasswordResetRequestSerializer,
    PasswordSerializer,
    RegistrationSerializer,
    TwoFactorAuthRequestSerializer,
    TwoFactorAuthVerifySerializer,
    VerifyEmailSerializer,
    PasswordRequestIdSerializer,
    EmailSerializer,
    PasswordResetRequestSerializerV2,
)
from ...exceptions import ValidationAPIException

logger = logging.getLogger(__name__)


class ApiHealthView(TradeRemediesApiView):
    """Health check.

    Perform a health check and return a status report.
    """

    @staticmethod
    def get(request, *args, **kwargs):
        """Get health.

        :returns (HttpResponse): health status.
        """
        return ResponseSuccess({"health": "OK"})


class EmailAvailabilityAPI(APIView):
    authentication_classes = ()

    @staticmethod
    def post(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        serializer = UserDoesNotExistSerializer(data=request.data)
        return ResponseSuccess({"result": {"available": serializer.is_valid()}})


# @method_decorator(axes_dispatch, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class AuthenticationView(APIView):
    authentication_classes = ()
    """Authentication View.
    Accepts a user's login credentials and returns an access token.
    """

    @staticmethod
    def post(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Arguments:
            request: a Django Request object, must contain in the POST body:
                - email: Valid email address.
                - password: Valid password.
        Returns:
            HttpResponse response with the user's token and user data
        Raises:
            AccessDenied if request fails.
        """
        """if not flag_enabled('ROI_USERS', group_name="V2_AUTH_GROUP", user_object=request.user):
            print("My feature flag is enabled")"""

        serializer = AuthenticationSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.validated_data["user"]
            email = serializer.validated_data["email"]
            invitation_code = request.data.get("invitation_code")

            login(request, user)  # Logging the user in
            reset(username=email)  # Reset any remaining access attempts
            Invitation.objects.validate_all_pending(
                user, invitation_code
            )  # validate all pending invitations

            return ResponseSuccess(serializer.data, http_status=status.HTTP_200_OK)
        else:
            raise ValidationAPIException(serializer_errors=serializer.errors)

    def perform_authentication(self, request):
        """Perform Authentication.

        Method required to perform lazy authentication of the user for this end point.
        """
        pass


class RegistrationAPIView(APIView):
    authentication_classes = ()

    @transaction.atomic  # noqa: C901
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response with the user's token and user data
            ResponseError response if the user could not be created  #todo - raise an error like the other views
        """
        serializer = RegistrationSerializer(
            data=request.data, context={"request": request}, many=False
        )
        if serializer.is_valid():
            # if code and case are provided, validate the invite, do not accept
            invitation = None
            code = serializer.initial_data["code"]
            case_id = serializer.initial_data["case_id"]

            if code and case_id:
                invitation = Invitation.objects.get_invite_by_code(code)
            if invitation:
                invited_organisation = invitation.organisation
                if group := invitation.organisation_security_group:
                    if group.name == SECURITY_GROUP_THIRD_PARTY_USER:
                        # Third Party's org is on the contact not the invite
                        invited_organisation = invitation.contact.organisation
                else:
                    invited_organisation = invitation.organisation
                # register interest if this is the first user of this organisation
                register_interest = not invited_organisation.has_users
                # If it's a third party invite, we don't want to create a registration of interest
                if invitation.submission.type.id == SUBMISSION_TYPE_INVITE_3RD_PARTY:
                    register_interest = False
                contact_kwargs = {}
                if serializer.initial_data["confirm_invited_org"] == "True":
                    contact_kwargs = {
                        "contact": invitation.contact,
                    }
                else:
                    register_interest = False
                accept = False
                groups = []
                if invitation.organisation_security_group:
                    # There is a group specified so add it
                    groups.append(invitation.organisation_security_group.name)
                    accept = True
                if invited_organisation.has_users:
                    groups.append(SECURITY_GROUP_ORGANISATION_USER)
                else:
                    groups.append(SECURITY_GROUP_ORGANISATION_OWNER)
                user = serializer.save(groups=groups, **contact_kwargs)
                invitation.process_invitation(
                    user, accept=accept, register_interest=register_interest
                )
            else:
                user = serializer.save()

            return ResponseSuccess({"result": user.to_dict()}, http_status=status.HTTP_201_CREATED)
        else:
            if serializer.errors.get("email", []) == ["User already exists."]:
                # If the email already exists,
                # notify the original user and pretend registration completed ok.
                user = serializer.get_user(serializer.initial_data["email"])
                template_id = SystemParameter.get("NOTIFY_EMAIL_EXISTS")
                send_mail(user.email, {"full_name": user.name}, template_id)

                return ResponseSuccess(
                    {
                        "result": {
                            "email": serializer.initial_data["email"],
                            "id": None,
                        }
                    },
                    http_status=status.HTTP_201_CREATED,
                )
            return ResponseError(serializer.errors)


class TwoFactorRequestAPI(TradeRemediesApiView):
    """Request or verify two-factor authentication"""

    @staticmethod
    def get(request, delivery_type: str = TwoFactorAuth.SMS, *args, **kwargs):
        """
        Sends a 2fa code to a user.

        Arguments:
            request: a Django Request object
            delivery_type: How you want the code to be sent - 'sms' or 'email'
        Returns:
            ResponseSuccess response with the 2fa delivery send report
        Raises:
            InvalidRequestParams if the code could not be sent
        """
        twofactorauth_object = request.user.twofactorauth
        if delivery_type == TwoFactorAuth.SMS and not request.user.phone:
            # We want to use email if we don't have their mobile number
            delivery_type = TwoFactorAuth.EMAIL

        serializer = TwoFactorAuthRequestSerializer(
            instance=twofactorauth_object,
            data={"delivery_type": delivery_type},
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return ResponseSuccess(serializer.data, http_status=status.HTTP_200_OK)
        else:
            raise ValidationAPIException(serializer_errors=serializer.errors)

    @staticmethod
    def post(request, *args, **kwargs):
        """
        Verifies a 2fa code provided by a user.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response with the user.to_dict() if the 2fa code is valid
        Raises:
            InvalidRequestParams if the code could could not be validated
        """
        twofactorauth_object = request.user.twofactorauth
        serializer = TwoFactorAuthVerifySerializer(
            instance=twofactorauth_object,
            data={"code": request.data.get("2fa_code", None)},
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return ResponseSuccess(serializer.data, http_status=status.HTTP_200_OK)
        else:
            raise ValidationAPIException(serializer_errors=serializer.errors)


class RequestPasswordReset(APIView):
    """Request and send a password reset email."""

    @staticmethod
    def get(request, *args, **kwargs):
        """
        Sends a password reset email.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response.
        """
        email = request.GET.get("email")
        serializer = EmailSerializer(data={"email": email})
        logger.info(f"Password reset request for: {email}")
        if serializer.is_valid():
            # Invalidate all previous PasswordResetRequest objects for this user
            PasswordResetRequest.objects.reset_request(email=email)
            return ResponseSuccess({"result": True})
        else:
            raise ValidationAPIException(serializer_errors=serializer.errors)


class RequestPasswordResetV2(APIView):
    """Request and send a password reset email."""

    @staticmethod
    def get(request, *args, **kwargs):
        """
        Sends a password reset email.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response.
        """
        request_id = request.GET.get("request_id")
        serializer = PasswordRequestIdSerializer(data={"request_id": request_id})
        logger.info(f"Password reset request {request_id}")
        if serializer.is_valid():
            # Invalidate all previous PasswordResetRequest objects for this user
            PasswordResetRequest.objects.reset_request_using_request_id(request_id=request_id)
            return ResponseSuccess({"result": True})
        else:
            raise ValidationAPIException(serializer_errors=serializer.errors)


class PasswordResetFormV2(APIView):
    """Verify a password reset link and allow user to use it."""

    @staticmethod
    def get(request, *args, **kwargs):
        """
        Verifies that a password reset link is valid.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response with a boolean response in the dictionary, True if valid, False if not.
        """
        serializer = PasswordResetRequestSerializerV2(data=request.GET)
        request_id = request.GET["request_id"]
        logger.info(f"Password reset link clicked for: request {request_id}")
        if valid := serializer.is_valid():
            logger.info(f"Password reset link valid for: request {request_id}")
        else:
            logger.info(f"Password reset link invalid for: request {request_id}")

        return ResponseSuccess({"result": valid})

    @staticmethod
    def post(request, *args, **kwargs):
        """
        Changes a user's password.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response if the password was successfully changed.
        Raises:
            InvalidRequestParams if link is invalid or password is not complex enough.
        """
        token_serializer = PasswordResetRequestSerializerV2(data=request.data)
        password_serializer = PasswordSerializer(data=request.data)
        request_id = request.data.get("request_id")

        if token_serializer.is_valid() and password_serializer.is_valid():
            if PasswordResetRequest.objects.password_reset_v2(
                token_serializer.initial_data["token"],
                token_serializer.initial_data["request_id"],
                token_serializer.initial_data["password"],
            ):
                logger.info(f"Password reset completed for: request {request_id}")
                user_pk = PasswordResetRequest.objects.get(request_id=request_id).user.pk
                user = User.objects.get(pk=user_pk)
                audit_log(audit_type=AUDIT_TYPE_PASSWORD_RESET, user=user)
                return ResponseSuccess({"result": {"reset": True}}, http_status=status.HTTP_200_OK)
        elif not password_serializer.is_valid():
            user_pk = PasswordResetRequest.objects.get(request_id=request_id).user.pk
            user = User.objects.get(pk=user_pk)
            audit_log(audit_type=AUDIT_TYPE_PASSWORD_RESET_FAILED, user=user)
            raise ValidationAPIException(serializer_errors=password_serializer.errors)
        else:
            logger.warning(f"Could not reset password for request {request_id}")
            user_pk = PasswordResetRequest.objects.get(request_id=request_id).user.pk
            user = User.objects.get(pk=user_pk)
            audit_log(audit_type=AUDIT_TYPE_PASSWORD_RESET_FAILED, user=user)
            raise InvalidRequestParams("Invalid or expired link")


class PasswordResetForm(APIView):
    """Verify a password reset link and allow user to use it."""

    @staticmethod
    def get(request, *args, **kwargs):
        """
        Verifies that a password reset link is valid.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response with a boolean response in the dictionary, True if valid, False if not.
        """
        serializer = PasswordResetRequestSerializer(data=request.GET)
        user_pk = request.GET["user_pk"]
        logger.info(f"Password reset link clicked for: {user_pk}")
        if valid := serializer.is_valid():
            logger.info(f"Password reset link valid for: {user_pk}")
        else:
            logger.info(f"Password reset link invalid for: {user_pk}")

        return ResponseSuccess({"result": valid})

    @staticmethod
    def post(request, *args, **kwargs):
        """
        Changes a user's password.

        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response if the password was successfully changed.
        Raises:
            InvalidRequestParams if link is invalid or password is not complex enough.
        """
        token_serializer = PasswordResetRequestSerializer(data=request.data)
        password_serializer = PasswordSerializer(data=request.data)
        user_pk = request.data.get("user_pk")

        if token_serializer.is_valid() and password_serializer.is_valid():
            if PasswordResetRequest.objects.password_reset(
                token_serializer.initial_data["token"],
                token_serializer.initial_data["user_pk"],
                token_serializer.initial_data["password"],
            ):
                logger.info(f"Password reset completed for: {user_pk}")
                return ResponseSuccess({"result": {"reset": True}}, http_status=status.HTTP_200_OK)
        elif not password_serializer.is_valid():
            raise ValidationAPIException(serializer_errors=password_serializer.errors)
        else:
            logger.warning(f"Could not reset password for user {user_pk}")
            raise InvalidRequestParams("Invalid or expired link")


class VerifyEmailAPI(TradeRemediesApiView):
    """Verifies if an email address belongs to a given user."""

    @staticmethod
    def post(request, code: str = None):
        """
        A multipurpose endpoint (for the moment), if code is provided it will verify the code is correct and note the
        email verification in the database.

        If code is not provided, it will send out a verification email to the request.user

        Arguments:
            request: a Django Request object
            code: an email verification code
        Returns:
            ResponseSuccess response if the email was validated / a new link was sent out.
        Raises:
            InvalidRequestParams if the link was incorrect.
        """
        if code:
            user = request.user
            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.filter(email_verify_code=code).first()
                user = profile.user

            serializer = VerifyEmailSerializer(data={"code": code}, context={"profile": profile})
            if serializer.is_valid():
                profile.email_verified_at = timezone.now()
                profile.save()
                user.refresh_from_db()
                return ResponseSuccess({"result": user.to_dict()})
            else:
                raise InvalidRequestParams(serializer.errors)
        elif not request.user.is_anonymous:
            response = request.user.userprofile.verify_email()
            return ResponseSuccess({"result": response})
        else:
            raise InvalidRequestParams("User unknown")
