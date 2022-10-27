from django.contrib.auth.models import Group
from django_restql.fields import NestedField
from rest_framework import serializers

from cases.models import Case
from config.serializers import CustomValidationModelSerializer
from contacts.models import Contact
from core.models import TwoFactorAuth, User
from core.utils import convert_to_e164


class TwoFactorAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwoFactorAuth
        exclude = ["user"]

    id = serializers.ReadOnlyField(source="user.id")  # One-to-One field which is also PK


class ContactSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"

    name = serializers.CharField(required=False)
    country = serializers.CharField(source="country.alpha3", required=False)
    organisation_name = serializers.ReadOnlyField(source="organisation.name")
    has_user = serializers.ReadOnlyField()

    def save(self, **kwargs):
        # If the 'country' is present in changed data, we need to fetch the true value from the dic
        if country := self.validated_data.get("country"):
            self.validated_data["country"] = country["alpha3"]

        # Let's internationalise the phone number and convert it to e164 format
        if phone := self.validated_data.get("phone"):
            # Checking the number hasn't already been internationalised
            if not phone.startswith("+"):
                # We need to figure out what country we are internationalising for, default to GB
                country = "GB"
                # If the instance has a country, let's use that
                if self.instance.country and self.instance.country.alpha3:
                    country = self.instance.country.alpha3
                # Even better, we can use the validated data which has just been passed in
                if self.validated_data.get("country"):
                    country = self.validated_data["country"]

                e164_phone = convert_to_e164(phone, country)
                self.validated_data["phone"] = e164_phone

        return super().save(**kwargs)


class UserSerializer(CustomValidationModelSerializer):
    class Meta:
        model = User
        exclude = ("password",)

    email = serializers.ReadOnlyField()
    cases = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()
    twofactorauth = TwoFactorAuthSerializer(required=False)
    contact = NestedField(serializer_class=ContactSerializer, required=False)

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
