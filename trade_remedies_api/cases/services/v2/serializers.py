from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from cases.models import Case, CaseType, Submission, SubmissionDocument, SubmissionDocumentType, \
    SubmissionStatus
from config.serializers import CustomValidationModelSerializer, NestedKeyField
from core.models import User
from core.services.v2.users.serializers import UserSerializer
from documents.services.v2.serializers import DocumentSerializer
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


class SubmissionStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionStatus
        fields = "__all__"


class SubmissionDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionDocumentType
        fields = "__all__"


class SubmissionDocumentSerializer(serializers.ModelSerializer):
    type = SubmissionDocumentTypeSerializer()
    document = DocumentSerializer()

    class Meta:
        model = SubmissionDocument
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
    status = NestedKeyField(
        queryset=SubmissionStatus.objects.all(),
        serializer=SubmissionStatusSerializer,
        required=False
    )
    paired_documents = SerializerMethodField(read_only=True)
    orphaned_documents = SerializerMethodField(read_only=True)
    submission_documents = SubmissionDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = "__all__"

    def create(self, validated_data):
        return Submission.objects.create(
            status=validated_data["type"].default_status,
            name=validated_data["type"].name,
            **validated_data
        )

    def get_paired_documents(self, instance):
        # We need to order the documents, so they come in pairs (confidential, non_confidential)
        paired_documents = []
        for submission_document in self.instance.submissiondocument_set.filter(type__key="respondent"):
            document = submission_document.document
            if document.parent:
                self_key = "confidential" if document.confidential else "non_confidential"
                other_key = "non_confidential" if document.confidential else "confidential"
                paired_documents.append({
                    self_key: DocumentSerializer(document).data,
                    other_key: DocumentSerializer(document.parent).data,
                    "orphan": False
                })

        return paired_documents

    def get_orphaned_documents(self, instance):
        # Get all the documents that do not have a corresponding public/private pair
        orphaned_documents = []
        for submission_document in self.instance.submissiondocument_set.filter(type__key="respondent"):
            document = submission_document.document
            if not document.parent and not document.document_set.exists():
                # The document is both not a parent and doesn't have any children - an orphan
                self_key = "confidential" if document.confidential else "non_confidential"
                other_key = "non_confidential" if document.confidential else "confidential"
                orphaned_documents.append({
                    self_key: DocumentSerializer(document).data,
                    other_key: None,
                    "orphan": True
                })

        return orphaned_documents
