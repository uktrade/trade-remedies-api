from django_restql.fields import NestedField
from rest_framework import serializers

from cases.services.v2.serializers import CaseSerializer
from config.serializers import CustomValidationModelSerializer
from contacts.models import CaseContact
from contacts.services.v2.serializers import CaseContactSerializer
from core.services.v2.users.serializers import UserSerializer
from organisations.services.v2.serializers import (
    OrganisationCaseRoleSerializer,
    OrganisationSerializer,
)
from security.models import CaseRole, OrganisationCaseRole, UserCase


class UserCaseSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserCase
        fields = "__all__"

    organisation = NestedField(
        serializer_class=OrganisationSerializer, required=False, accept_pk=True, fields=["name"]
    )
    case = NestedField(
        serializer_class=CaseSerializer,
        required=False,
        accept_pk=True,
        fields=["name", "reference"],
    )
    user = NestedField(
        serializer_class=UserSerializer,
        required=False,
        accept_pk=True,
        fields=["name", "email"],
    )
    organisation_case_role = serializers.SerializerMethodField()
    case_contact = serializers.SerializerMethodField()

    @staticmethod
    def get_organisation_case_role(instance):
        # Returns the OrganisationCaseRole associated with this UserCase
        try:
            org_case_role = OrganisationCaseRole.objects.get(
                case=instance.case, organisation=instance.organisation
            )
            return OrganisationCaseRoleSerializer(org_case_role).data
        except OrganisationCaseRole.DoesNotExist:
            return None

    @staticmethod
    def get_case_contact(instance):
        case_contacts = CaseContact.objects.filter(
            case=instance.case, contact=instance.user.contact, organisation=instance.organisation
        )
        if case_contacts:
            return CaseContactSerializer(case_contacts.first()).data
        return None


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
