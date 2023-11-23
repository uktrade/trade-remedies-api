from django_restql.fields import NestedField
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from cases.models import (
    Case,
    CaseType,
    ExportSource,
    Product,
    Submission,
    SubmissionDocument,
    SubmissionDocumentType,
    SubmissionStatus,
    SubmissionType,
)
from config.serializers import CustomValidationModelSerializer
from core.services.v2.users.serializers import ContactSerializer, UserSerializer
from documents.services.v2.serializers import DocumentSerializer
from organisations.services.v2.serializers import OrganisationSerializer


class CaseTypeSerializer(CustomValidationModelSerializer):
    class Meta:
        model = CaseType
        fields = "__all__"


class ProductSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"

    hs_codes = serializers.SerializerMethodField()

    @staticmethod
    def get_hs_codes(instance):
        return [each.code for each in instance.hs_codes.all()]


class ExportSourceSerializer(CustomValidationModelSerializer):
    class Meta:
        model = ExportSource
        fields = "__all__"

    country = serializers.ReadOnlyField(source="country.name", required=False)


class CaseSerializer(CustomValidationModelSerializer):
    reference = serializers.CharField(required=False)
    type = NestedField(serializer_class=CaseTypeSerializer, required=False, accept_pk=True)
    initiated_at = serializers.DateTimeField(required=False)
    registration_deadline = serializers.DateTimeField(required=False)
    product_set = ProductSerializer(many=True, required=False)
    exportsource_set = ExportSourceSerializer(many=True, required=False)

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


class SubmissionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionType
        fields = "__all__"


class SubmissionSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Submission
        fields = "__all__"

    case = NestedField(serializer_class=CaseSerializer, required=False, accept_pk=True)
    organisation = NestedField(
        serializer_class=OrganisationSerializer, required=False, accept_pk=True
    )
    documents = NestedField(serializer_class=DocumentSerializer, many=True, required=False)
    created_by = NestedField(
        serializer_class=UserSerializer,
        required=False,
        accept_pk=True,
        fields=["name", "email"],
    )
    status = NestedField(
        serializer_class=SubmissionStatusSerializer, required=False, accept_pk=True
    )
    paired_documents = SerializerMethodField(read_only=True)
    orphaned_documents = SerializerMethodField(read_only=True)
    submission_documents = NestedField(
        serializer_class=SubmissionDocumentSerializer, many=True, read_only=True
    )
    contact = NestedField(serializer_class=ContactSerializer, required=False, accept_pk=True)
    type = NestedField(serializer_class=SubmissionTypeSerializer, required=False, accept_pk=True)
    primary_contact = NestedField(
        serializer_class=ContactSerializer, required=False, accept_pk=True
    )
    parent = serializers.SerializerMethodField()
    deficiency_notices = serializers.SerializerMethodField()
    organisation_name = serializers.ReadOnlyField(source="organisation.name")
    organisation_case_role_name = serializers.ReadOnlyField()
    is_tra = serializers.ReadOnlyField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data = data.copy()

        # If the request has a query param of non_confidential_only=True, then we need to filter
        # out any confidential documents
        if request := self.context.get("request"):
            if request.GET.get("non_confidential_only") == "True":
                data["submission_documents"] = [
                    each
                    for each in data["submission_documents"]
                    if not each["document"]["confidential"]
                ]
        return data

    @staticmethod
    def eager_load_queryset(queryset):
        """Eager load all the fields in the queryset"""
        queryset = queryset.select_related("organisation", "primary_contact")
        queryset = queryset.prefetch_related("documents")
        return queryset

    @staticmethod
    def get_parent(instance):
        if parent := instance.parent:
            return SubmissionSerializer(parent, exclude=["organisation"]).data

    @staticmethod
    def get_deficiency_notices(instance):
        parent_deficiency_documents = instance.get_parent_deficiency_documents()
        if parent_deficiency_documents:
            return SubmissionDocumentSerializer(parent_deficiency_documents, many=True).data
        return None

    def create(self, validated_data):
        return Submission.objects.create(
            status=validated_data["type"].default_status,
            name=validated_data["type"].name,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if deficiency_notice_params := validated_data.pop("deficiency_notice_params", None):
            # we're updating the deficiency_notice_params field, it's a JSONField so let's update,
            # rather than overwrite
            if not instance.deficiency_notice_params:
                instance.deficiency_notice_params = {}
            instance.deficiency_notice_params.update(deficiency_notice_params)
        return super().update(instance, validated_data)

    def get_paired_documents(self, instance):
        # We need to order the documents, so they come in pairs (confidential, non_confidential)
        paired_documents = []
        for submission_document in instance.submissiondocument_set.filter(
            type__key="respondent", deleted_at__isnull=True
        ):
            document = submission_document.document
            if document.parent:
                self_key = "confidential" if document.confidential else "non_confidential"
                other_key = "non_confidential" if document.confidential else "confidential"

                try:
                    self_submission_document = document.submissiondocument_set.get(
                        submission=instance
                    )
                    other_submission_document = document.parent.submissiondocument_set.get(
                        submission=instance
                    )
                except SubmissionDocument.DoesNotExist:
                    # something has gone quite wrong, let's skip
                    continue
                self_dict = DocumentSerializer(document).data
                self_dict.update(
                    {
                        "sufficient": self_submission_document.sufficient,
                        "deficient": self_submission_document.deficient,
                    }
                )

                other_dict = DocumentSerializer(document.parent).data
                other_dict.update(
                    {
                        "sufficient": other_submission_document.sufficient,
                        "deficient": other_submission_document.deficient,
                    }
                )

                paired_documents.append(
                    {
                        self_key: self_dict,
                        other_key: other_dict,
                        "orphan": False,
                    }
                )

        return paired_documents

    def get_orphaned_documents(self, instance):
        # Get all the documents that do not have a corresponding public/private pair
        orphaned_documents = []
        for submission_document in instance.submissiondocument_set.filter(type__key="respondent"):
            document = submission_document.document
            if not document.parent and not document.document_set.exists():
                # The document is both not a parent and doesn't have any children - an orphan
                self_key = "confidential" if document.confidential else "non_confidential"
                other_key = "non_confidential" if document.confidential else "confidential"
                orphaned_documents.append(
                    {
                        self_key: DocumentSerializer(document).data,
                        other_key: {},
                        "orphan": True,
                        "deficient": submission_document.deficient,
                        "sufficient": submission_document.sufficient,
                    }
                )

        return orphaned_documents


class PublicFileSerializer(serializers.Serializer):
    submission_id = serializers.UUIDField()
    submission_name = serializers.CharField()
    issued_at = serializers.DateTimeField()
    organisation_name = serializers.CharField()
    organisation_case_role_name = serializers.CharField()
    no_of_files = serializers.IntegerField()
    is_tra = serializers.BooleanField()
    deficiency_notice_params = serializers.JSONField(required=False, allow_null=True)
