from rest_framework import serializers

from cases.models import Case, CaseType, Submission
from config.serializers import CustomValidationModelSerializer
from documents.seriaizers import DocumentSerializer
from organisations.serializers import OrganisationSerializer


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
        fields = "__all__"


class SubmissionSerializer(serializers.ModelSerializer):
    case = CaseSerializer()
    organisation = OrganisationSerializer()
    documents = DocumentSerializer(many=True)

    class Meta:
        model = Submission
        fields = "__all__"
