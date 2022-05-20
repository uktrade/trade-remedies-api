import logging

from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from config.serializers import CustomValidationModelSerializer
from core.exceptions import CustomValidationError
from core.models import SystemParameter, User, UserProfile
from core.services.auth.serializers import EmailAvailabilitySerializer, EmailSerializer, \
    PasswordSerializer
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationUser

logger = logging.getLogger(__name__)


class RegistrationSerializer(
    EmailAvailabilitySerializer, PasswordSerializer, serializers.ModelSerializer
):
    """Registration serializer used to register new users on the platform.

    Validates if registrations are currently being accepted (marked by the REGISTRATION_SOFT_LOCK system parameter) and
    if they have confirmed they represent the organisation in question.

    Also deals with the creation of this new user using the relevant method (create_user) on the User manager.
    """

    code = serializers.CharField(required=False, allow_blank=True)
    case_id = serializers.CharField(required=False, allow_blank=True)
    confirm_invited_org = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "password", "name", "code", "case_id", "confirm_invited_org"]

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs=attrs)
        password = attrs["password"]
        if SystemParameter.get("REGISTRATION_SOFT_LOCK") and not password.startswith(
                SystemParameter.get("REGISTRATION_SOFT_LOCK_KEY")
        ):
            raise ValidationError(
                _("Registrations are currently locked."), code="registration_locked"
            )

        if attrs.get("code") and attrs.get("case_id") and not attrs.get("confirm_invited_org"):
            raise ValidationError(
                {"organisation_name": _("Organisation name is required.")},
                code="organisation_name_required",
            )

        return attrs

    def save(self, **kwargs):
        if not self.instance:  # This is a new user
            # We need the initial_data as it contains the POST data used to create the User, e.g. organisation_name
            # It gets overridden by the validated_data

            # Very very strange, unpacking the initial_data dictionary turns strings into lists, need to revert
            new_initial_data = dict(self.initial_data)
            nid = {}
            for key, value in new_initial_data.items():
                if isinstance(value, list):
                    nid[key] = value[0]
                else:
                    nid[key] = value[0]
            validated_data = {**nid, **self.validated_data, **kwargs}
            new_user = User.objects.create_user(**validated_data)
            new_user.userprofile.verify_email()
            return new_user
        return super().save(**kwargs)


class V2RegistrationSerializer(
    EmailAvailabilitySerializer, PasswordSerializer, CustomValidationModelSerializer
):
    class Meta:
        model = User
        fields = ["email", "password", "name"]

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        password = attrs["password"]
        if SystemParameter.get("REGISTRATION_SOFT_LOCK") and not password.startswith(
                SystemParameter.get("REGISTRATION_SOFT_LOCK_KEY")
        ):
            raise ValidationError(
                _("Registrations are currently locked."), code="registration_locked"
            )
        return attrs

    def save(self, **kwargs):
        if not self.instance:  # This is a new user
            new_user = User.objects.create_user(
                contact_country=self.initial_data["mobile_country_code"],
                contact_address=self.initial_data["address_snippet"],
                contact_post_code=self.initial_data["address"]["postal_code"],
                contact_phone=self.initial_data["mobile"],
                **self.validated_data
            )
            self.instance = new_user
            organisation = Organisation.objects.create_or_update_organisation(
                user=new_user,
                assign_user=True,
                name=self.initial_data["name"],
                address=self.initial_data["address_snippet"],
                country=self.initial_data["country"],
                post_code=self.initial_data["address"]["postal_code"],
                vat_number=self.initial_data["company_vat_number"],
                eori_number=self.initial_data["company_eori_number"],
                duns_number=self.initial_data["company_duns_number"],
                organisation_website=self.initial_data["company_website"],
                companies_house_id=self.initial_data["company_number"],
            )
            security_group_name = OrganisationUser.objects.user_organisation_security_group(
                new_user, organisation
            )
            new_user.groups.add(security_group_name)  # Add the user to same group
            new_user.userprofile.verify_email()
            return new_user
        else:
            return super().save(**kwargs)

    @property
    def data(self):
        return {
            "email": self.instance.email,
            "pk": self.instance.pk
        }


class VerifyEmailSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["email_verify_code"]

    def validate_email_verify_code(self, value):
        if value == self.instance.email_verify_code:
            return value
        raise CustomValidationError(error_key="wrong_email_verification_code")

    def save(self, **kwargs):
        self.instance.email_verified_at = timezone.now()
        return self.instance.save()
