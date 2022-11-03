from cases.services.v2.serializers import CaseSerializer
from config.serializers import CustomValidationModelSerializer
from organisations.services.v2.serializers import (
    OrganisationCaseRoleSerializer,
    OrganisationSerializer,
)
from security.models import OrganisationCaseRole, UserCase
from rest_framework import serializers


class UserCaseSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserCase
        fields = "__all__"

    organisation = OrganisationSerializer(fields=["name"])
    case = CaseSerializer(fields=["name", "reference"])
    organisation_case_role = serializers.SerializerMethodField()

    @staticmethod
    def get_organisation_case_role(instance):
        # Returns the OrganisationCaseRole associated with this UserCase
        org_case_role = OrganisationCaseRole.objects.get(
            case=instance.case, organisation=instance.organisation
        )
        return OrganisationCaseRoleSerializer(org_case_role).data
