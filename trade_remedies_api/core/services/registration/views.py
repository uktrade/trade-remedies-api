import json

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView

from core.models import SystemParameter
from core.notifier import send_mail
from core.services.base import ResponseError, ResponseSuccess
from invitations.models import Invitation
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)
from core.services.registration.serializers import RegistrationSerializer, V2RegistrationSerializer


class V2RegistrationAPIView(CreateAPIView):
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
        registration_data = json.loads(request.POST["registration_data"])
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
                    user, accept=accept, register_interest=register_interest, newly_registered=True
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
