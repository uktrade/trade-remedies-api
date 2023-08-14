import os

from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from documents.models import Document
from cases.models import SubmissionType
from documents.models import Document, DocumentBundle


class DocumentSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"

    is_uploaded_document = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    truncated_name = serializers.SerializerMethodField()
    size_in_kb = serializers.SerializerMethodField()

    @staticmethod
    def get_is_uploaded_document(instance: Document) -> bool:
        """
        Returns True if the document in question has been uploaded by a PUBLIC user.
        Parameters
        ----------
        value : a Document object

        Returns
        -------
        bool
        """
        return not instance.system

    @staticmethod
    def get_extension(instance: Document) -> str:
        """Returns the extension of the document file.

        e.g. test-document.pdf ---> pdf
        """

        filename, file_extension = os.path.splitext(instance.name)
        return file_extension[1:]

    @staticmethod
    def get_truncated_name(instance: Document) -> str:
        """Returns the truncated document name.

        e.g. super_long_document_name_this_is_ridiculous.pdf ---> super_long_doc...iculous.pdf"""

        if len(instance.name) > 35:
            return f"{instance.name[0:18]}...{instance.name[-18:]}"
        return instance.name

    @staticmethod
    def get_size_in_kb(instance: Document) -> str:
        """Returns the size of the document in kilobytes."""
        return f"{int(instance.size)/(1<<10):,.0f}"


class DocumentBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentBundle
        fields = "__all__"

    documents = DocumentSerializer(many=True)
    submission_type = serializers.SlugRelatedField(
        slug_field="name", queryset=SubmissionType.objects.all()
    )
