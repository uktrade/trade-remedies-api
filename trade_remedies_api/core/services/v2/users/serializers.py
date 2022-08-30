from django.contrib.auth.models import Group
from rest_framework import serializers

from cases.models import Case
from contacts.models import Contact
from core.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ("password",)

    cases = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()

    def get_cases(self, instance):
        from cases.services.v2.serializers import CaseSerializer

        return [CaseSerializer(each).data for each in Case.objects.user_cases(user=instance)]

    def get_organisation(self, instance):
        """Gets the organisation that this user belongs to.

        Provides an exclude argument to the OrganisationSerializer to avoid recursive infinite
        serialization.
        """
        from organisations.services.v2.serializers import OrganisationSerializer

        if organisation_user_object := instance.organisation:
            return OrganisationSerializer(
                instance=organisation_user_object.organisation, exclude=["organisationuser_set"]
            ).data


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"

    country = serializers.ReadOnlyField(source="country.alpha3")
    organisation_name = serializers.ReadOnlyField(source="organisation.name")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"

    def to_internal_value(self, data):
        data = data.copy()  # Making the QueryDict mutable
        if security_group := data.get("security_group"):
            # We can pass a security group in the request.POST which we can use
            # to look up a Group object
            role_object = Group.objects.get(name=security_group)
            data[""] = role_object.pk
        return super().to_internal_value(data)
