from config.viewsets import BaseModelViewSet
from core.models import Feedback
from core.services.v2.feedback.serializers import FeedbackSerializer


class FeedbackViewSet(BaseModelViewSet):
    queryset = Feedback.objects.all().order_by("-created_at")
    serializer_class = FeedbackSerializer
