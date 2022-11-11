from cases.services.v2.serializers import CaseSerializer
from config.serializers import CustomValidationModelSerializer
from organisations.services.v2.serializers import OrganisationSerializer
from security.models import CaseRole, UserCase


class UserCaseSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserCase
        fields = "__all__"

    organisation = OrganisationSerializer(fields=["name"])
    case = CaseSerializer(fields=["name", "reference"])


class CaseRoleSerializer(CustomValidationModelSerializer):
    class Meta:
        model = CaseRole
        fields = "__all__"

    def to_internal_value(self, data):
        """API requests can pass case_role with the key"""
        data = data.copy()  # Making the QueryDict mutable
        if role_key := data.get("role_key"):
            # We can pass a role_key in the request.POST which we can use to lookup a CaseRole obj
            role_object = CaseRole.objects.get(key=role_key)
            data["role"] = role_object.pk
        return super().to_internal_value(data)
