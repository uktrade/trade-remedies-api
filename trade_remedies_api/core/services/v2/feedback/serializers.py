from django_restql.fields import NestedField

from config.serializers import CustomValidationModelSerializer
from core.models import Feedback
from core.services.v2.users.serializers import UserSerializer


class FeedbackSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"

    user = NestedField(serializer_class=UserSerializer, accept_pk=True)
