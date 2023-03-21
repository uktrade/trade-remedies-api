from django.contrib.auth.models import Group
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from config.viewsets import BaseModelViewSet
from contacts.models import CaseContact, Contact
from core.models import TwoFactorAuth, User
from core.services.v2.users.serializers import (
    ContactSerializer,
    TwoFactorAuthSerializer,
    UserSerializer,
)
from organisations.models import Organisation


class UserViewSet(BaseModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer

    @extend_schema(
        summary="Check if user is in group",
        parameters=[
            OpenApiParameter(
                "group_name",
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        methods=["get"],
        responses={
            200: inline_serializer(
                name="BooleanResponse",
                fields={
                    "user_is_in_group": serializers.BooleanField(),
                },
            )
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_name="user_in_group",
    )
    def is_user_in_group(self, request, *args, **kwargs):
        user = User.objects.get(pk=kwargs["pk"])
        is_in_group = user.groups.filter(name=request.query_params.get("group_name")).exists()
        return Response({"user_is_in_group": is_in_group})

    @extend_schema(
        request={"group_name": str},
        methods=["put"],
        responses={200: UserSerializer},
    )
    @action(detail=True, methods=["put"], url_name="change_group", url_path="change_group")
    def add_group(self, request, *args, **kwargs):
        """
        Adds the user defined by the user_pk url argument to the group_name in request data
        """
        group_object = Group.objects.get(name=request.data["group_name"])
        user_object = User.objects.get(pk=kwargs["pk"])
        group_object.user_set.add(user_object)
        group_object.save()
        return self.retrieve(request, *args, **kwargs)

    @extend_schema(
        request={"group_name": str},
        methods=["delete"],
        responses={200: UserSerializer},
    )
    @add_group.mapping.delete
    def delete_group(self, request, *args, **kwargs):
        """
        Deletes the user defined by the user_pk url argument from the group_name in request data
        """
        group_object = Group.objects.get(name=request.data["group_name"])
        user_object = User.objects.get(pk=kwargs["pk"])
        user_object.groups.remove(group_object)
        return self.retrieve(request, *args, **kwargs)

    @extend_schema(
        methods=["get"],
        responses={
            200: UserSerializer,
            404: OpenApiTypes.STR,
        },
        examples=[
            OpenApiExample(
                "User Not Found",
                value="User with email test@example.com does not exist",  # /PS-IGNORE
                response_only=True,
                status_codes=["404"],
            )
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        url_name="get_user_by_email",
        url_path="get_user_by_email/(?P<user_email>\S+)",
    )
    def get_user_by_email(self, request, user_email, *args, **kwargs):
        """Returns a serialized User object queried using a case-sensitive email address.

        Raises a 404 if a user with that email is not found.
        """
        try:
            # email needs to be exact and unique
            user_object = User.objects.get(email__exact=user_email)
            return Response(UserSerializer(user_object).data)
        except User.DoesNotExist:
            return Response(
                data=f"User with email {user_email} does not exist",
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        methods=["get"],
        responses={200: UserSerializer},
    )
    @action(
        detail=True,
        methods=["get"],
        url_name="send_verification_email",
        url_path="send_verification_email",
    )
    def send_verification_email(self, request, *args, **kwargs):
        """Sends a verification email to the user."""
        self.get_object().userprofile.verify_email()
        return self.retrieve(request)


NOT_FOUND_RESPONSE = OpenApiExample(
    "Not Found",
    description="Not Found",
    value={"detail": "Not found."},
    response_only=True,
    status_codes=["404"],
)


class ContactViewSet(BaseModelViewSet):
    """
    ModelViewSet for interacting with contact objects via the API.
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    @extend_schema(
        methods=["patch"],
        request=inline_serializer(
            "case_id_organisation_serializer",
            fields={
                "case_id": serializers.UUIDField(),
                "organisation_id": serializers.UUIDField(required=False),
                "primary": serializers.ChoiceField(choices=("yes", "no"), required=False),
            },
        ),
        responses={
            200: ContactSerializer,
            404: OpenApiTypes.OBJECT,
        },
        examples=[NOT_FOUND_RESPONSE],
    )
    @action(
        detail=True,
        methods=["patch"],
        url_name="add_to_case",
        url_path="add_to_case",
    )
    def add_to_case(self, request, *args, **kwargs):
        """Adds this contact to a case by creating a CaseContact object. If an organisation_id is
        provided in the request body, then the CaseContact object will be associated with the
        relevant Organisation object.
        """

        from cases.models import Case

        case_object = get_object_or_404(Case, pk=request.data["case_id"])
        contact_object = self.get_object()

        organisation_object = contact_object.organisation
        if organisation_id := request.data.get("organisation_id"):
            # we will use the contact organisation by default (they are representing themselves)
            # unless we get an organisation_id in the request
            organisation_object = get_object_or_404(Organisation, pk=organisation_id)

        primary = request.data.get("primary", "no")
        CaseContact.objects.get_or_create(
            case=case_object,
            contact=contact_object,
            organisation=organisation_object,
            primary=True if primary == "yes" else False,
        )

        return self.retrieve(request)

    @extend_schema(
        methods=["patch"],
        request={"organisation_id": str},
        responses={
            200: ContactSerializer,
            404: OpenApiTypes.OBJECT,
        },
        examples=[NOT_FOUND_RESPONSE],
    )
    @action(
        detail=True,
        methods=["patch"],
        url_name="change_organisation",
        url_path="change_organisation",
    )
    def change_organisation(self, request, *args, **kwargs):
        """Changes the organisation of the contact."""
        from organisations.models import Organisation

        organisation_object = get_object_or_404(Organisation, pk=request.data["organisation_id"])
        contact_object = self.get_object()
        contact_object.organisation = organisation_object
        contact_object.save()

        return self.retrieve(request)


class TwoFactorAuthViewSet(BaseModelViewSet):
    """ModelViewSet for interacting with TwoFactorAuth objects."""

    queryset = TwoFactorAuth.objects.all()
    serializer_class = TwoFactorAuthSerializer
