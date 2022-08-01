import os

from rest_framework import serializers

from documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"

    is_uploaded_document = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    is_public_document = serializers.SerializerMethodField()

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

    def get_is_public_document(self, instance):
        print("asd")
