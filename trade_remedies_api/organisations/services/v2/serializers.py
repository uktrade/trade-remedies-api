from django.contrib.auth.models import Group
from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import UserSerializer
from organisations.models import Organisation
from security.models import CaseRole, OrganisationCaseRole, OrganisationUser


class OrganisationUserSerializer(CustomValidationModelSerializer):
    class Meta:
        model = OrganisationUser
        fields = "__all__"

    user = UserSerializer()
    security_group = serializers.SlugRelatedField(slug_field="name", queryset=Group.objects.all())


class OrganisationSerializer(CustomValidationModelSerializer):
    country = serializers.SerializerMethodField()
    organisationuser_set = OrganisationUserSerializer(many=True)

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
