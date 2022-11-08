from django_restql.fields import NestedField

from config.serializers import CustomValidationModelSerializer
from contacts.models import CaseContact
from core.services.v2.users.serializers import ContactSerializer


class CaseContactSerializer(CustomValidationModelSerializer):
    class Meta:
        model = CaseContact
        fields = "__all__"

    contact = NestedField(serializer_class=ContactSerializer, required=False)
