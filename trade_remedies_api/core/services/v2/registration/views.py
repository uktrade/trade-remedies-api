import json
import logging
import uuid

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from rest_framework import status
from rest_framework.views import APIView

from core.exceptions import ValidationAPIException
from core.models import SystemParameter, User
from core.notifier import send_mail
from core.services.base import ResponseSuccess
from core.services.v2.registration.serializers import (
    V2RegistrationSerializer,
    VerifyEmailSerializer,
)


class V2RegistrationAPIView(APIView):
    authentication_classes = ()
    serializer_class = V2RegistrationSerializer

    @transaction.atomic  # noqa: C901
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Arguments:
            request: a Django Request object
        Returns:
            ResponseSuccess response with the user's token and user data
            ResponseError response if the user could not be created  #todo - raise an error like the other views
        """
        registration_data = json.loads(request.data["registration_data"])
        serializer = V2RegistrationSerializer(data=registration_data)
        if serializer.is_valid():
            serializer.save()
            return ResponseSuccess({"result": serializer.data}, http_status=status.HTTP_201_CREATED)
        else:
            if "User already exists." in serializer.errors.get("email", []).detail:
                # If the email already exists,
                # notify the original user and pretend registration completed ok.
                user = User.objects.get(email=serializer.initial_data["email"])
                template_id = SystemParameter.get("NOTIFY_EMAIL_EXISTS")
                send_mail(user.email, {"full_name": user.name}, template_id)

                return ResponseSuccess(
                    {
                        "result": {
                            "email": serializer.initial_data["email"],
                            "pk": uuid.uuid4(),  # Give them a random UUID
                        }
                    },
                    http_status=status.HTTP_201_CREATED,
                )
            else:
                raise ValidationAPIException(serializer_errors=serializer.errors)


class EmailVerifyAPIView(APIView):
    """Multipurpose API endpoint dealing with sending and verifying email verification links."""

    def post(self, request, user_pk, email_verify_code=None, *args, **kwargs):
        try:
            user_object = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            logging.error(f"User with pk {user_pk} does not exist.")
            return ResponseSuccess()
        else:
            if email_verify_code:
                # We want to verify the code, not send a new one
                serializer = VerifyEmailSerializer(
                    instance=user_object.userprofile, data={"email_verify_code": email_verify_code}
                )
                if serializer.is_valid():
                    serializer.save()
                else:
                    raise ValidationAPIException(serializer_errors=serializer.errors)
            else:
                # We want to send a new email verification link
                user_object.userprofile.verify_email()
            return ResponseSuccess(data={"result": user_object.to_dict()})
