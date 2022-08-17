from django.contrib.auth.models import Group
from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer, NestedKeyField
from invitations.models import Invitation
from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationSerializer


class InvitationSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Invitation
        fields = "__all__"

    organisation = NestedKeyField(
        queryset=Organisation.objects.all(), serializer=OrganisationSerializer, required=False
    )
    organisation_id = serializers.ReadOnlyField(source="organisation.id")
    organisation_name = serializers.ReadOnlyField(source="organisation.name")
    organisation_security_group = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Group.objects.all(),
        required=False
    )
