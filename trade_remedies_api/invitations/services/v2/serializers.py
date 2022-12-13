from django.contrib.auth.models import Group
from django_restql.fields import NestedField
from rest_framework import serializers

from cases.services.v2.serializers import CaseSerializer, SubmissionSerializer
from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import ContactSerializer, UserSerializer
from invitations.models import Invitation
from organisations.services.v2.serializers import OrganisationSerializer
from security.services.v2.serializers import UserCaseSerializer


class InvitationSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Invitation
        fields = "__all__"

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
