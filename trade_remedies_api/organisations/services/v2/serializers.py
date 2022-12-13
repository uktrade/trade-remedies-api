from django.contrib.auth.models import Group
from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import UserSerializer
from organisations.models import Organisation
from security.models import CaseRole, OrganisationCaseRole, OrganisationUser, UserCase


class OrganisationCaseRoleSerializer(CustomValidationModelSerializer):
    case = serializers.SerializerMethodField()
    case_role_key = serializers.SerializerMethodField()

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

    @staticmethod
    def get_case(instance):
        # This needs to be a SerializerMethodField to avoid the circular import of CaseSerializer
        from cases.services.v2.serializers import CaseSerializer

        return CaseSerializer(instance=instance.case).data

    @staticmethod
    def get_case_role_key(instance):
        return instance.role.key


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
    organisationcaserole_set = OrganisationCaseRoleSerializer(many=True, required=False)
    user_cases = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = "__all__"

    def get_user_cases(self, instance):
        user_cases = UserCase.objects.filter(
            user__organisationuser__organisation=instance,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        )

        from security.services.v2.serializers import UserCaseSerializer

        return UserCaseSerializer(user_cases, many=True).data

    @staticmethod
    def get_country(instance):
        return instance.country.alpha3

    def get_cases(self, instance):
        """Return all cases that this organisation is a part of."""
        from cases.services.v2.serializers import CaseSerializer

        cases = UserCase.objects.filter(
            user__organisationuser__organisation=instance,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        ).select_related("case")
        if request := self.context.get("request", None):
            cases = cases.filter(user=request.user)
        return [CaseSerializer(each.case).data for each in cases]

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
