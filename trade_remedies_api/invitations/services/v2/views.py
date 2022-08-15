from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from django.conf import settings
from contacts.models import Contact
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer


class InvitationViewSet(viewsets.ModelViewSet):
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        invitation_object = serializer.save(
            user_context=self.request.user,
            created_by=self.request.user,
        )
        invitation_object.create_codes()
        invitation_object.save()
        return invitation_object

    def perform_update(self, serializer):
        if "name" in serializer.validated_data and "email" in serializer.validated_data:
            # We want to create a new Contact object to associate with this Invitation, only if the
            # invitation object doesn't already have a contact or the contact associated with the
            # invitation has different name/email to the submitted
            if (serializer.instance.contact and (
                    serializer.instance.contact.name != serializer.validated_data["name"] or
                    serializer.instance.contact.email != serializer.validated_data["email"]
            ) or not serializer.instance.contact):
                contact_object = Contact.objects.create(
                    created_by=self.request.user,
                    name=serializer.validated_data["name"],
                    email=serializer.validated_data["email"],
                    user_context=self.request.user
                )

                # Updating the meta dictionary to reflect the changes
                serializer.instance.meta = {
                    "name": serializer.validated_data["name"],
                    "email": serializer.validated_data["email"]
                }
                serializer.instance.contact = contact_object
                serializer.save()
        return super().perform_update(serializer)

    @action(detail=True, methods=["post"], url_name="send_invitation")
    def send_invitation(self, request, *args, **kwargs):
        """
        Adds the user defined by the user_pk url argument to the group_name in request data
        """
        invitation_object = self.get_object()
        invitation_object.draft = False
        invitation_object.save()
        invitation_object.send(
            sent_by=request.user,
            direct=False,
            template_key="NOTIFY_INVITE_ORGANISATION_USER",
            context={
                "login_url": f"{settings.PUBLIC_ROOT_URL}/invitation/{invitation_object.code}/"
                             f"for/{invitation_object.organisation.id}/"
            },
        )
        return self.retrieve(request)
