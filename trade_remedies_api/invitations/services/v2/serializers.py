from django.contrib.auth.models import Group
from django_restql.fields import NestedField
from rest_framework import serializers

from cases.services.v2.serializers import CaseSerializer, SubmissionSerializer
from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import ContactSerializer, UserSerializer
from invitations.models import Invitation
from organisations.services.v2.serializers import OrganisationSerializer
from security.models import CaseRole
from security.services.v2.serializers import UserCaseSerializer


class InvitationSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Invitation
        fields = "__all__"

    created_by = UserSerializer(required=False, fields=["name", "email"])
    organisation = NestedField(
        serializer_class=OrganisationSerializer,
        required=False,
        accept_pk=True,
        exclude=["cases", "invitations", "organisationuser_set"],
    )
    contact = NestedField(serializer_class=ContactSerializer, required=False, accept_pk=True)

    organisation_id = serializers.ReadOnlyField(source="organisation.id")
    organisation_name = serializers.ReadOnlyField(source="organisation.name")
    organisation_security_group = serializers.SlugRelatedField(
        slug_field="name", queryset=Group.objects.all(), required=False
    )
    submission = NestedField(
        serializer_class=SubmissionSerializer,
        exclude=["organisation", "created_by"],
        required=False,
    )
    invited_user = NestedField(
        serializer_class=UserSerializer, required=False, exclude=["organisation"], accept_pk=True
    )
    cases_to_link = NestedField(serializer_class=CaseSerializer, many=True, required=False)
    user_cases_to_link = NestedField(serializer_class=UserCaseSerializer, many=True, required=False)
    case = NestedField(required=False, serializer_class=CaseSerializer, accept_pk=True)
    authorised_signatory = NestedField(
        required=False, serializer_class=ContactSerializer, accept_pk=True
    )
    type_display_name = serializers.ReadOnlyField(source="get_invitation_type_display")
    status = serializers.SerializerMethodField()

    @staticmethod
    def get_status(instance):
        """Helper function to return a machine and human-readable status. (obviously they're both
        machine-readable but YOU KNOW WHAT I MEAN.

        CHOICES:

        "draft" - Draft
        "accepted" - Accepted
        "invite_sent" - Invite sent
        "waiting_tra_review" - Waiting TRA review
        "rejected_by_tra" - Rejected by the TRA
        "deficient" - Deficient
        """
        choices = {
            "draft": "Draft",
            "accepted": "Accepted",
            "invite_sent": "Invite sent",
            "waiting_tra_review": "Waiting TRA Approval",
            "rejected_by_tra": "Rejected by the TRA",
            "approved_by_tra": "Approved by the TRA",
            "deficient": "Deficient",
            "unknown": "Unknown",  # this should never happen
        }
        status = "unknown"

        if not instance.email_sent:
            status = "draft"
        elif instance.invitation_type in [1, 3]:
            # an own-org or caseworker invitation, there are really only 3 states:
            # 1. draft
            # 2. invite sent
            # 3. accepted
            if instance.accepted_at:
                status = "accepted"
            else:
                status = "invite_sent"
        elif instance.invitation_type == 2:
            # a rep invitation is a bit more complex, they are related to a submission and can have
            # a number of states:
            # 1. draft - invitation in progress
            # 2. invite sent - invitation sent but not accepted
            # 3. waiting tra review - invitation accepted but not yet approved by the TRA
            # 4. rejected by tra - invitation rejected by the TRA
            # 5. approved by tra - invitation approved by the TRA
            # 6. deficient - submission associated with the invitation is deficient
            if instance.submission.status.version:
                status = "deficient"
            elif instance.rejected_at:
                status = "rejected_by_tra"
            elif instance.approved_at:
                status = "approved_by_tra"
            elif not instance.accepted_at and not instance.submission.status.received:
                status = "invite_sent"
            elif not instance.approved_at and not instance.rejected_at:
                status = "waiting_tra_review"

        verbose_status = choices[status]
        return status, verbose_status

    def to_internal_value(self, data):
        """API requests can pass case_role with the key"""
        data = data.copy()  # Making the QueryDict mutable
        if role_key := data.get("case_role_key"):
            # We can pass a role_key in the request.POST which we can use to lookup a CaseRole obj
            role_object = CaseRole.objects.get(key=role_key)
            data["case_role"] = role_object.pk
        return super().to_internal_value(data)
