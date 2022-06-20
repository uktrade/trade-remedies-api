from rest_framework import serializers

from cases.models import Case, CaseType
from config.serializers import CustomValidationModelSerializer


class CaseTypeSerializer(CustomValidationModelSerializer):
    class Meta:
        model = CaseType
        fields = "__all__"


class CaseSerializer(CustomValidationModelSerializer):
    reference = serializers.CharField()
    type = CaseTypeSerializer()
    case_status = serializers.JSONField()
    initiated_at = serializers.DateTimeField()
    registration_deadline = serializers.DateTimeField()

    class Meta:
        model = Case
        fields = '__all__'
