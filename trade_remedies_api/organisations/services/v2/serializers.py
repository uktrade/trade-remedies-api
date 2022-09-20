from django.contrib.auth.models import Group
from django.db.models import F, Q
from rest_framework import serializers

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission
from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import UserSerializer
from invitations.models import Invitation
from organisations.models import Organisation
from security.models import CaseRole, OrganisationCaseRole, OrganisationUser, UserCase


class OrganisationUserSerializer(CustomValidationModelSerializer):
    class Meta:
        model = OrganisationUser
        fields = "__all__"

    user = UserSerializer()
    security_group = serializers.SlugRelatedField(slug_field="name", queryset=Group.objects.all())


class OrganisationSerializer(CustomValidationModelSerializer):
    country = serializers.SerializerMethodField()
    organisationuser_set = OrganisationUserSerializer(many=True, required=False)
    cases = serializers.SerializerMethodField()
    invitations = serializers.SerializerMethodField()
    validated = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = "__all__"

    def get_country(self, obj):
        return obj.country.alpha3

    def get_cases(self, instance):
        """Return all cases that this organisation is a part of."""
        from cases.services.v2.serializers import CaseSerializer
        case_serializers = []
        cases = UserCase.objects.filter(
            user__organisationuser__organisation=instance,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        ).select_related("case")
        if request := self.context.get("request", None):
            cases = cases.filter(user=request.user)

        # query parameter no_representative_cases determines if we only want the cases where this
        # organisation is a direct contributor, and NOT a representative cases
        if self.context.get("request", None) and request.GET.get("no_representative_cases"):
            for user_case in cases:
                # Now let's work out if the organisation is an
                # interested party or a representative for each case
                invitation_query = Invitation.objects.filter(
                    Q(case=user_case.case), Q(contact__organisation=instance)
                    # Exclude those Invitations where the contact org == org, as
                    # those are normal invite
                ).exclude(contact__organisation=F("organisation"))

                if not invitation_query.exists():
                    # This organisation was not invited to the case as part of a third party invite.
                    case_serializers.append(CaseSerializer(user_case.case).data)
        else:
            case_serializers = [CaseSerializer(user_case.case).data for user_case in cases]

        case_serializers.sort(key=lambda x: x["name"])

        return case_serializers

    def get_invitations(self, instance):
        """Return all invitations that this organisation has sent."""
        from invitations.services.v2.serializers import InvitationSerializer

        return [
            InvitationSerializer(
                instance=each, exclude=["organisation"]  # Avoid infinite self-referencing
            ).data
            for each in instance.invitation_set.all().select_related(
                "organisation", "contact", "submission"
            )
        ]

    def get_validated(self, instance):
        """Returns true if the organisation has been validated on the TRS at some point"""
        return instance.organisationcaserole_set.filter(validated_at__isnull=False).exists()


class OrganisationCaseRoleSerializer(CustomValidationModelSerializer):
    class Meta:
        model = OrganisationCaseRole
        fields = "__all__"
        extra_kwargs = {"case": {"read_only": True}, "organisation": {"read_only": True}}

    def to_internal_value(self, data):
        data = data.copy()  # Making the QueryDict mutable
        if role_key := data.get("role_key"):
            # We can pass a role_key in the request.POST which we can use to lookup a CaseRole obj
            role_object = CaseRole.objects.get(key=role_key)
            data["role"] = role_object.pk
        return super().to_internal_value(data)
