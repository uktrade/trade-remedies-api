import logging

from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from audit import AUDIT_TYPE_EMAIL_VERIFIED, AUDIT_TYPE_LOGIN, AUDIT_TYPE_USER_CREATED
from audit.utils import audit_log
from config.serializers import CustomValidationModelSerializer
from core.exceptions import CustomValidationError
from core.models import SystemParameter, User, UserProfile
from core.services.auth.serializers import (
    UserDoesNotExistSerializer,
    UserExistsSerializer,
    PasswordSerializer,
)
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationUser

logger = logging.getLogger(__name__)


class V2RegistrationSerializer(
    UserDoesNotExistSerializer, PasswordSerializer, CustomValidationModelSerializer
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
                contact_post_code=self.initial_data["post_code"],
                contact_phone=self.initial_data["mobile"],
                **self.validated_data
            )
            self.instance = new_user
            organisation = Organisation.objects.create_or_update_organisation(
                user=new_user,
                assign_user=True,
                name=self.initial_data["company_name"],
                address=self.initial_data["address_snippet"],
                country=self.initial_data["country"],
                post_code=self.initial_data["post_code"],
                vat_number=self.initial_data["company_vat_number"],
                eori_number=self.initial_data["company_eori_number"],
                duns_number=self.initial_data["company_duns_number"],
                organisation_website=self.initial_data["company_website"],
                companies_house_id=self.initial_data["company_number"],
                contact_object=new_user.contact,
            )
            security_group_name = OrganisationUser.objects.user_organisation_security_group(
                new_user, organisation
            )
            new_user.groups.add(security_group_name)  # Add the user to same group
            audit_log(audit_type=AUDIT_TYPE_USER_CREATED, user=new_user)
            return new_user
        else:
            return super().save(**kwargs)

    @property
    def data(self):
        return {"email": self.instance.email, "pk": self.instance.pk}


class VerifyEmailSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["email_verify_code"]

    def validate_email_verify_code(self, value):
        if value == self.instance.email_verify_code:
            return value
        raise CustomValidationError(error_key="wrong_email_verification_code")

    def save(self, **kwargs):
        if not self.instance.email_verified_at:
            # If they have already verified their email, we don't want to overwrite the time
            self.instance.email_verified_at = timezone.now()
            audit_log(audit_type=AUDIT_TYPE_EMAIL_VERIFIED, user=self.instance.user)
        return self.instance.save()
