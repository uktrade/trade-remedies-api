from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from organisations.models import Organisation
from security.models import OrganisationCaseRole


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
