import json
from core.services.base import TradeRemediesApiView, ResponseSuccess
from notes.models import Note
from documents.models import Document
from rest_framework import status
from audit import AUDIT_TYPE_ATTACH
from core.services.exceptions import InvalidRequestParams, NotFoundApiExceptions
from core.utils import get_content_type
from cases.models import get_case


class NoteAPIView(TradeRemediesApiView):
    """
    Get or create Notes on other models

    ### GET

    `GET /api/v1/notes/case/{CASE_UUID}/` Get all case notes
    `GET /api/v1/notes/case/{CASE_UUID}/on/{CONTENT_TYPE_IDENTIFIER}/{MODEL_ID}/`
    Get all notes for a particular model
    `GET /api/v1/notes/{NOTE_UUID}/` Get a specific note

    ### POST

    `POST /api/v1/notes/case/{CASE_UUID}/on/{CONTENT_TYPE_IDENTIFIER}/{MODEL_ID}/` Create a new note
    `POST /api/v1/notes/{NOTE_UUID}/` Update a specific note
    `GET /api/v1/notes/case/{CASE_UUID}/` Shortcut to create a note directly on a case.
    """

    def get(
        self,
        request,
        note_id=None,
        model_id=None,
        content_type=None,
        case_id=None,
        model_key=None,
        *args,
        **kwargs,
    ):
        if note_id:
            try:
                note = Note.objects.get(id=note_id)
                return ResponseSuccess({"result": note.to_dict()})
            except Note.DoesNotExist:
                raise NotFoundApiExceptions("Invalid note id")
        else:
            notes = Note.objects.filter(deleted_at__isnull=True)
        if case_id:
            notes = notes.filter(case__id=case_id)
        if model_id and content_type:
            _content_type = get_content_type(content_type)
            if model_key:
                notes = notes.filter(
                    model_id=model_id, content_type=_content_type, model_key=model_key
                )
            else:
                notes = notes.filter(model_id=model_id, content_type=_content_type)

        else:
            raise InvalidRequestParams("A note id, case id or a model identifiers are required")
        notes = notes.order_by("created_at")
        return ResponseSuccess({"results": [_note.to_dict() for _note in notes]})

    def post(  # noqa: C901
        self,
        request,
        case_id=None,
        note_id=None,
        model_id=None,
        document_id=None,
        content_type=None,
        *args,
        **kwargs,
    ):
        """
        create / update the Notes
        :param request:
        :param note_id:
        :param model_id:
        :param args:
        :param kwargs:
        :return:
        """
        case = get_case(case_id)
        _file = request.data.get("document", None)
        _file = json.loads(_file) if isinstance(_file, str) else None
        document = None
        if _file:
            document = Document.objects.create_document(
                file=_file,
                user=request.user,
                case=case,
                confidential=request.data.get("confidentiality") == "confidential",
            )
            document_id = document.id
        if document_id:
            document = Document.objects.get(id=document_id)
            confidentiality = request.data.get("confidentiality")
            if confidentiality in ["confidential", "non-confidential"]:
                document.confidential = confidentiality == "confidential"
                document.save()

        if note_id:
            try:
                note = Note.objects.get(id=note_id, case__id=case_id)
            except Note.DoesNotExist:
                raise NotFoundApiExceptions("Invalid note id")
        else:
            model_id = model_id or request.data.get("model_id")
            content_type = content_type or request.data.get("content_type")
            if not model_id and not content_type:
                model_id = case_id
                _content_type = get_content_type("cases.case")
            else:
                _content_type = get_content_type(content_type)
            note = Note(
                case=case,
                created_by=request.user,
                model_id=model_id,
                content_type=_content_type,
                user_context=[request.user],
            )
        note.load_attributes(request.data, ["note", "model_key"])
        if document:
            note.documents.add(document)
            note.set_user_context([request.user])
            note.generic_audit(
                message=f"Document attached: {document.name}",
                audit_type=AUDIT_TYPE_ATTACH,
                id=str(document.id),
            )
        if note.is_dirty():
            note.save()
        return ResponseSuccess({"result": note.to_dict()}, http_status=status.HTTP_201_CREATED)

    def delete(
        self,
        request,
        case_id=None,
        note_id=None,
        model_id=None,
        document_id=None,
        content_type=None,
        *args,
        **kwargs,
    ):
        response = None
        if note_id and document_id:
            try:
                note = Note.objects.get(id=note_id, case__id=case_id)
                document = Document.objects.get(id=document_id)
                case = get_case(case_id)
                # Only delete if the doc is not used in any submissions
                if len(document.submissions(case)) == 0:
                    note.documents.remove(document)
                    response = document.delete()
                else:
                    result = {"deleted": False, "result": "Document used in submission"}
            except Note.DoesNotExist:
                raise NotFoundApiExceptions("Invalid note id")
        else:
            raise NotFoundApiExceptions("Invalid note id")

        return ResponseSuccess({"result": {"deleted": True, "result": response}})
