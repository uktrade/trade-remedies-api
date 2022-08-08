import os

from rest_framework import serializers

from documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"

    is_uploaded_document = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    truncated_name = serializers.SerializerMethodField()

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

    def get_extension(self, instance: Document) -> str:
        """Returns the extension of the document file.

        e.g. test-document.pdf ---> pdf
        """

        filename, file_extension = os.path.splitext(instance.name)
        return file_extension[1:]

    def get_truncated_name(self, instance):
        """Returns the truncated document name.

        e.g. super_long_document_name_this_is_ridiculous.pdf ---> super_long_doc...iculous.pdf"""

        if len(instance.name) > 25:
            return f'{instance.name[0:10]}...{instance.name[-10:]}'
        return instance.name
