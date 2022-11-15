from config.viewsets import BaseModelViewSet
from contacts.models import CaseContact
from contacts.services.v2.serializers import CaseContactSerializer


class CaseContactViewSet(BaseModelViewSet):
    queryset = CaseContact.objects.all()
    serializer_class = CaseContactSerializer
