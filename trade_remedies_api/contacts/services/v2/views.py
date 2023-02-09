from config.viewsets import BaseModelViewSet
from contacts.models import CaseContact, Contact
from contacts.services.v2.serializers import CaseContactSerializer


class CaseContactViewSet(BaseModelViewSet):
    """ModelViewSet for interacting with CaseContact objects."""

    queryset = CaseContact.objects.all()
    serializer_class = CaseContactSerializer
