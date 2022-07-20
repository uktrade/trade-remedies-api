from rest_framework import serializers

from cases.models import Case, CaseType, Submission
from config.serializers import CustomValidationModelSerializer, NestedKeyField
from core.models import User
from core.services.v2.users.serializers import UserSerializer
from documents.seriaizers import DocumentSerializer
from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationSerializer


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
    case = NestedKeyField(queryset=Case.objects.all(), serializer=CaseSerializer)
    organisation = NestedKeyField(
        queryset=Organisation.objects.all(),
        serializer=OrganisationSerializer,
        required=False
    )
    documents = DocumentSerializer(many=True, required=False)
    created_by = NestedKeyField(
        queryset=User.objects.all(),
        serializer=UserSerializer
    )

    class Meta:
        model = Submission
        fields = "__all__"

    def create(self, validated_data):
        return Submission.objects.create(
            status=validated_data["type"].default_status,
            name=validated_data["type"].name,
            **validated_data
        )
