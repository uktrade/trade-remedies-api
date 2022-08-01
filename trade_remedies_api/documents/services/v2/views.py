from rest_framework import status, viewsets
from rest_framework.response import Response

from cases.models import Submission, SubmissionDocumentType
from documents.models import Document
from documents.services.v2.serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def create(self, request, *args, **kwargs):
        submission_object = Submission.objects.get(id=request.POST["submission_id"])
        parent_document_object = None
        if parent_document_id := request.POST.get("parent"):
            parent_document_object = Document.objects.get(id=parent_document_id)

        # Creating the Document object
        document = Document.objects.create_document(
            file={
                "name": request.POST["stored_name"],
                "size": request.POST["file_size"],
                "document_name": request.POST["original_name"]
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
        document_object = self.get_object()
        for submission_object in document_object.submission_set.all():
            document_object.set_case_context(submission_object.case)

            # Deleting all child documents
            for child_document in document_object.document_set.all():
                submission_object.remove_document(child_document, requested_by=request.user)
                child_document.delete()

            # Removing the document in question from the submission
            submission_object.remove_document(document_object, requested_by=request.user)

        # Finally, deleting the document object itself
        document_object.delete()

        return Response(status=204)
