from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from contacts.models import Contact
from core.models import TwoFactorAuth, User, UserProfile
from core.services.v2.users.serializers import UserSerializer
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
            user=self.request.user,
        )
        invitation_object.create_codes()

        # If this is a representative invite (a third party invite), we also want to create a
        # submission object associated with this invitation
        if invitation_object.invitation_type == 2:
            submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
            submission_status = submission_type.default_status
            submission_object = Submission.objects.create(
                name="Invite 3rd party",
                type=submission_type,
                status=submission_status,
                case=invitation_object.case,
                created_by=self.request.user,
                contact=self.request.user.contact,
            )
            invitation_object.submission = submission_object
        invitation_object.save()

        return invitation_object

    def perform_update(self, serializer):
        if "name" in serializer.validated_data and "email" in serializer.validated_data:
            # We want to create a new Contact object to associate with this Invitation, only if the
            # invitation object doesn't already have a contact or the contact associated with the
            # invitation has different name/email to the submitted
            if (
                    serializer.instance.contact
                    and (
                    serializer.instance.contact.name != serializer.validated_data["name"]
                    or serializer.instance.contact.email != serializer.validated_data["email"]
            )
                    or not serializer.instance.contact
            ):
                contact_object = Contact.objects.create(
                    created_by=self.request.user,
                    name=serializer.validated_data["name"],
                    email=serializer.validated_data["email"],
                    user_context=self.request.user,
                )

                # Updating the meta dictionary to reflect the changes
                serializer.instance.meta = {
                    "name": serializer.validated_data["name"],
                    "email": serializer.validated_data["email"],
                }
                serializer.instance.contact = contact_object
                serializer.save()

        if security_group := serializer.validated_data.get("organisation_security_group", None):
            # we need to update the meta dictionary of the invitation to reflect the group
            serializer.instance.meta["group"] = security_group.name
            serializer.save()

        return super().perform_update(serializer)

    @action(detail=True, methods=["post"], url_name="send_invitation")
    def send_invitation(self, request, *args, **kwargs):
        """
        Adds the user defined by the user_pk url argument to the group_name in request data
        """
        invitation_object = self.get_object()
        invitation_object.draft = False

        if invitation_object.invitation_type == 1:
            # This is an invitation from within the organisation
            invitation_object.send(
                sent_by=request.user,
                direct=False,
                template_key="NOTIFY_INVITE_ORGANISATION_USER",
                context={
                    "login_url": f"{settings.PUBLIC_ROOT_URL}/case/accept_invite/"
                                 f"{invitation_object.id}/start/"
                },
            )
        elif invitation_object.invitation_type == 2:
            # This is a representative invite, send the appropriate email

            # we need to determine if the user being invited already has an account
            if User.objects.filter(email__iexact=invitation_object.contact.email).exists():
                # The user exists
                template_name = "NOTIFY_EXISTING_THIRD_PARTY_INVITE"
                link = f"{settings.PUBLIC_ROOT_URL}/accounts/login/"
            else:
                # The user does not exist
                template_name = "NOTIFY_NEW_THIRD_PARTY_INVITE"
                link = f"{settings.PUBLIC_ROOT_URL}/register/start"  # no trailing dash

            send_report = invitation_object.send(
                sent_by=request.user,
                context={
                    "organisation_you_are_representing": invitation_object.organisation.name,
                    "case_name": invitation_object.case.name,
                    "case_reference": invitation_object.case.reference,
                    "person_who_invited_you": invitation_object.user.name,
                    "link": link,
                },
                direct=True,
                template_key=template_name,
            )

            # We also need to update the submission status to sent
            invitation_object.submission.update_status("sufficient", request.user)

        invitation_object.sent_at = timezone.now()
        invitation_object.save()
        return self.retrieve(request)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_name="create_user_from_invitation")
    def create_user_from_invitation(self, request, *args, **kwargs):
        invitation_object = self.get_object()
        contact_object = invitation_object.contact

        # First we create the basic user object
        new_user, _ = User.objects.get_or_create(
            email=contact_object.email,
            defaults={
                "name": contact_object.name,
                "is_active": False
            }
        )

        # Then we set a password
        new_user.set_password(request.data["password"])

        # Then we create a UserProfile and TwoFactorAuth object
        TwoFactorAuth.objects.get_or_create(user=new_user)
        UserProfile.objects.get_or_create(
            user=new_user,
            defaults={
                "contact": None,
                "colour": "black"
            }
        )
        new_user.save()
        invitation_object.invited_user = new_user
        invitation_object.save()
        return Response(UserSerializer(new_user).data)
