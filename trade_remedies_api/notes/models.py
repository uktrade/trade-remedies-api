from django.db import models
from core.base import BaseModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres import fields


class Note(BaseModel):
    """
    Notes are able to attach to any model by a combination of model id and it's Django content type
    references. There is one exception to this for notes which are attached to workflow nodes.
    The note is then using model_key to determine the actual node the note is attached to,
    the case and the model id and content type of the CaseWorkflow model.
    For example, to get all notes for a case workflow, the CaseWorkflow id would be used, and then
    the model_key further down to distinguish notes across their respective nodes.
    """

    note = models.TextField(null=True, blank=True)
    model_id = models.UUIDField(null=False, blank=False)
    model_key = models.CharField(max_length=250, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, null=False, blank=False, on_delete=models.PROTECT)
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.PROTECT)
    documents = models.ManyToManyField("documents.Document", blank=True)
    data = fields.JSONField(null=True, blank=True)

    class Meta:
        index_together = ["content_type", "model_id"]

    def __str__(self):
        return self.note

    @staticmethod
    def for_model(model, descending=True):
        order = "-created_at" if descending else "created_at"
        content_type = ContentType.objects.get_for_model(model)
        return Note.objects.filter(content_type=content_type, model_id=model.id).order_by(order)

    @property
    def all_documents(self):
        return self.documents.filter(deleted_at__isnull=True)

    @property
    def all_non_issued_documents(self):
        return self.all_documents.exclude(document__submissiondocument__isnull=False)

    def _to_dict(self):
        _dict = {
            "note": self.note,
            "model_id": str(self.model_id),
            "content_type": self.content_type.model if self.content_type else None,
            "model_key": self.model_key,
            "documents": [doc.to_embedded_dict(case=self.case) for doc in self.all_documents],
            "case": {
                "id": str(self.case.id),
                "name": self.case.name,
                "sequence": self.case.sequence,
            }
            if self.case
            else None,
            "data": self.data,
        }
        return _dict
