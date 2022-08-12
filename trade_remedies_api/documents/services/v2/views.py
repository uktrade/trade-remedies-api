from rest_framework import status, viewsets
from rest_framework.response import Response

from cases.models import Submission, SubmissionDocumentType
from documents.models import Document, DocumentBundle
from documents.services.v2.serializers import DocumentBundleSerializer, DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def create(self, request, *args, **kwargs):
        """Endpoint for creating a new document object. Will also associate it with a submission
        if a submission_id is passed in the request.POST.
        """
        submission_object = Submission.objects.get(id=request.POST["submission_id"])
        parent_document_object = None
        if parent_document_id := request.POST.get("parent"):
            parent_document_object = Document.objects.get(id=parent_document_id)

        # Creating the Document object
        document = Document.objects.create_document(
            file={
                "name": request.POST["stored_name"],
                "size": request.POST["file_size"],
                "document_name": request.POST["original_name"],
            },
            user=request.user,
            confidential=True if request.POST["type"] == "confidential" else False,
            system=False,
            parent=parent_document_object,
            case=submission_object.case,
        )

        # Adding the document to the submission
        if submission_document_type := request.POST.get("submission_document_type", None):
            # You can pass a submission document type key
            submission_document_type = SubmissionDocumentType.objects.get(
                key=submission_document_type
            )
        else:
            submission_document_type = SubmissionDocumentType.type_by_user(request.user)
        submission_object.add_document(
            document=document,
            document_type=submission_document_type,
            issued=False,
            issued_by=request.user,
        )
        serializer = self.serializer_class(instance=document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Endpoint for deleting a Document object when given a PK, will also delete all child
        document objects and related SubmissionDocument objects.
        """
        document_object = self.get_object()

        # First dissociating this object from its parent
        document_object.parent = None
        document_object.save()

        # Marking all child documents as orphans
        for child_document in document_object.document_set.all():
            child_document.parent = None
            child_document.save()

        for submission_object in document_object.submission_set.all():
            document_object.set_case_context(submission_object.case)
            '''submission_object.remove_document(child_document, requested_by=request.user)
            child_document.delete()'''

            # Removing the document in question from the submission
            submission_object.remove_document(document_object, requested_by=request.user)

        # Finally, deleting the document object itself
        if s3_file := document_object.file.file:
            s3_file.obj.delete()  # deleting from S3
        document_object.delete()  # deleting reference from the DB

        return Response(status=204)


class DocumentBundleViewSet(viewsets.ModelViewSet):
    queryset = DocumentBundle.objects.all()
    serializer_class = DocumentBundleSerializer

    def retrieve(self, request, *args, **kwargs):
        print("ads")
