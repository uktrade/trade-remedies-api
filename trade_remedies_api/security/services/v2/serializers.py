from cases.services.v2.serializers import CaseSerializer
from config.serializers import CustomValidationModelSerializer
from organisations.services.v2.serializers import OrganisationSerializer
from security.models import UserCase


class UserCaseSerializer(CustomValidationModelSerializer):
    class Meta:
        model = UserCase
        fields = "__all__"

    organisation = OrganisationSerializer(fields=["name"])
    case = CaseSerializer(fields=["name", "reference"])
