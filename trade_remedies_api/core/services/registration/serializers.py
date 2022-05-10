import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.models import SystemParameter, User
from core.services.auth.serializers import EmailAvailabilitySerializer, PasswordSerializer

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
