from config.viewsets import BaseModelViewSet
from security.models import UserCase
from security.services.v2.serializers import UserCaseSerializer


class UserCaseViewSet(BaseModelViewSet):
    queryset = UserCase.objects.all()
    serializer_class = UserCaseSerializer
