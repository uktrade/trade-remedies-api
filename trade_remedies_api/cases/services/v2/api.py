from rest_framework import viewsets

from cases.models import Case, Submission
from cases.serializers import CaseSerializer, SubmissionSerializer


class CaseViewSet(viewsets.ModelViewSet):
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def get_queryset(self):
        if self.request.query_params.get("open_to_roi"):
            # We only want the cases which are open to registration of interest applications
            return Case.objects.available_for_regisration_of_intestest(self.request.user)
        return super().get_queryset()


class SubmissionViewSet(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
