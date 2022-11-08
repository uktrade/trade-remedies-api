from django.conf import settings
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.viewsets import BaseModelViewSet
from contacts.models import CaseContact, Contact
from core.models import User
from core.services.v2.users.serializers import UserSerializer
from invitations.models import Invitation
from invitations.services.v2.serializers import InvitationSerializer
from security.constants import SECURITY_GROUP_THIRD_PARTY_USER
from security.models import UserCase


class InvitationViewSet(BaseModelViewSet):
    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer

    def get_queryset(self):
        """We can filter the queryset using GET query parameters.

        type_id: the type of submission associated with the invitation
        contact_organisation_id: the ID of the organisation the contact of the invitation is part of
        """
        queryset = super().get_queryset()
        if type_id := self.request.GET.get("type_id"):
            queryset = queryset.filter(submission__type_id=type_id)
        if contact_organisation_id := self.request.GET.get("contact_organisation_id"):
            queryset = queryset.filter(contact__organisation_id=contact_organisation_id)
        return queryset

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
            invitation_object.organisation_security_group = Group.objects.get(
                name=SECURITY_GROUP_THIRD_PARTY_USER
            )
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
                    country=serializer.instance.organisation.country,
                    post_code=serializer.instance.organisation.post_code,
                )
                if serializer.instance.invitation_type == 1:
                    # This is an invitation from your own org, we can set the organisation of
                    # the contact object now. Representative invites get changed later on when
                    # the rep organisation is selected  /PS-IGNORE
                    contact_object.organisation = serializer.instance.organisation
                    contact_object.save()

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

        if user_cases_to_link := self.request.POST.getlist("user_cases_to_link"):
            # First we need to remove already-linked cases
            serializer.instance.user_cases_to_link.through.objects.filter(
                invitation=serializer.instance
            ).delete()

            if "choose_user_case_later" not in user_cases_to_link:
                # We want to link cases to this invitation
                user_case_objects = UserCase.objects.filter(id__in=user_cases_to_link)
                serializer.instance.user_cases_to_link.add(*user_case_objects)
                serializer.save()

        if updated_contact := serializer.validated_data.get("contact"):
            # Let's create a CaseContact to link the contact to the case

            if original_contact := serializer.instance.contact:
                # first let's delete the previous one if it exists
                CaseContact.objects.filter(
                    contact=original_contact,
                    case=serializer.instance.case,
                    organisation=serializer.instance.organisation,
                ).delete()

            # creating the new one with the updated contact
            CaseContact.objects.filter(
                contact=updated_contact,
                case=serializer.instance.case,
                organisation=serializer.instance.organisation,  # the inviting organisation
            )

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
            user_query = User.objects.filter(email__iexact=invitation_object.contact.email)
            if user_query.exists():
                # The user exists
                template_name = "NOTIFY_EXISTING_THIRD_PARTY_INVITE"
                link = f"{settings.PUBLIC_ROOT_URL}/accounts/login/"
                # we want to associate the invitation with them so it is processed on next login
                invitation_object.invited_user = user_query.get()
                invitation_object.save()
            else:
                # The user does not exist
                template_name = "NOTIFY_NEW_THIRD_PARTY_INVITE"
                link = (
                    f"{settings.PUBLIC_ROOT_URL}/case/accept_representative_invite/"
                    f"{invitation_object.id}/start/"
                )

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
                footer_case_email=False,
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

        new_user = User.objects.create_new_user(
            email=contact_object.email,
            name=contact_object.name,
            password=request.data.get("password", None),
            contact=contact_object,
            is_active=False,
            raise_exception=False,
        )
        invitation_object.invited_user = new_user
        invitation_object.save()

        return Response(UserSerializer(new_user).data)
