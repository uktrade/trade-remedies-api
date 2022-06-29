from flags.sources import Flag
from rest_framework import viewsets

class FlagViewSet(viewsets.ModelViewSet):
    renderer_classes = [APIResponseRenderer]
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def get_queryset(self):
        if self.request.query_params.get("open_to_roi"):
            # We only want the cases which are open to registration of interest applications
            return Case.objects.available_for_regisration_of_intestest(self.request.user)
        return super().get_queryset()
