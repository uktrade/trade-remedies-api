from django.contrib.auth.models import Group
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from contacts.models import Contact
from core.models import TwoFactorAuth, User
from core.services.v2.users.serializers import (
    ContactSerializer,
    TwoFactorAuthSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(
        detail=True,
        methods=["get"],
        url_name="user_in_group",
    )
    def is_user_in_group(self, request, *args, **kwargs):
        user = User.objects.get(pk=kwargs["pk"])
        is_in_group = user.groups.filter(name=request.query_params.get("group_name")).exists()
        return Response({"user_is_in_group": is_in_group})

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

    @add_group.mapping.delete
    def delete_group(self, request, *args, **kwargs):
        """
        Deletes the user defined by the user_pk url argument from the group_name in request data
        """
        group_object = Group.objects.get(name=request.data["group_name"])
        user_object = User.objects.get(pk=kwargs["pk"])
        user_object.groups.remove(group_object)
        return self.retrieve(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["get"],
        url_name="get_user_by_email",
        url_path="get_user_by_email/(?P<user_email>\S+)",
    )
    def get_user_by_email(self, request, user_email, *args, **kwargs):
        """Returns a serialized User object queried using a case-insensitive email address.

        Raises a 404 if a user with that email is not found.
        """
        try:
            user_object = User.objects.get(email__iexact=user_email)
            return Response(UserSerializer(user_object).data)
        except User.DoesNotExist:
            return Response(
                data=f"User with email {user_email} does not exist",
                status=status.HTTP_404_NOT_FOUND,
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


class ContactViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for interacting with contact objects via the API.
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer


class TwoFactorAuthViewSet(viewsets.ModelViewSet):
    """ModelViewSet for interacting with TwoFactorAuth objects."""

    queryset = TwoFactorAuth.objects.all()
    serializer_class = TwoFactorAuthSerializer
