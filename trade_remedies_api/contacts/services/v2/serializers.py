from django_restql.fields import NestedField

from config.serializer_fields import StringNestedField
from config.serializers import CustomValidationModelSerializer
from contacts.models import CaseContact
from core.services.v2.users.serializers import ContactSerializer


class CaseContactSerializer(CustomValidationModelSerializer):
    class Meta:
        model = CaseContact
        fields = "__all__"

    contact = NestedField(serializer_class=ContactSerializer, required=False, accept_pk=True)
    organisation = StringNestedField(
        serializer_module="organisations.services.v2.serializers",
        serializer_class_name="OrganisationSerializer",
        required=False,
        accept_pk=True
    )
    case = StringNestedField(
        serializer_module="cases.services.v2.serializers",
        serializer_class_name="CaseSerializer",
        required=False,
        accept_pk=True
    )
