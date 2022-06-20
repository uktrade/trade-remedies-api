from rest_framework import viewsets

from cases.models import Case
from cases.serializers import CaseSerializer
from core.renderers import APIResponseRenderer
from core.services.base import ResponseSuccess


class CaseViewSet(viewsets.ModelViewSet):
    renderer_classes = [APIResponseRenderer]
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def get_queryset(self):
        if self.request.query_params.get("open_to_roi"):
            # We only want the cases which are open to registration of interest applications
            return Case.objects.available_for_regisration_of_intestest(self.request.user)
        return super().get_queryset()
