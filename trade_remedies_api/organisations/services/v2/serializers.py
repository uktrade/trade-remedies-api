from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from organisations.models import Organisation
from security.models import CaseRole, OrganisationCaseRole


class OrganisationSerializer(CustomValidationModelSerializer):
    country = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = "__all__"

    def get_country(self, obj):
        return obj.country.alpha3


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
