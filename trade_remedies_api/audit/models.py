import datetime
import uuid
import json
from functools import singledispatch
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres import fields
from django.conf import settings
from . import (
    AUDIT_TYPE_UPDATE,
    AUDIT_TYPE_CREATE,
    AUDIT_TYPE_DELETE,
    AUDIT_TYPE_PURGE,
    AUDIT_TYPE_RESTORE,
    AUDIT_TYPE_READ,
    AUDIT_TYPE_LOGIN,
    AUDIT_TYPE_LOGOUT,
    AUDIT_TYPE_EVENT,
    AUDIT_TYPE_ATTACH,
    AUDIT_TYPE_NOTIFY,
    AUDIT_TYPE_DELIVERED,
)


@singledispatch
def extract_text(item):
    return item


@extract_text.register(list)
def _(item):
    return ", ".join(item)


@extract_text.register(dict)
def _(item):
    return item.get("name")


@extract_text.register(bool)
def _(item):
    return str(item)


class Audit(models.Model):
    """
    Audit records actions made by users.
    Actions can relate to models and include additional information regarding the action.
    For example, editing a model would record the time of edit and the values changed.
    Audit items can also be related to a specific case.
    Important audit logs (created manually) should be marked as milestone
    """

    AUDIT_TYPES = (
        (AUDIT_TYPE_UPDATE, "Update"),
        (AUDIT_TYPE_CREATE, "Create"),
        (AUDIT_TYPE_DELETE, "Delete"),
        (AUDIT_TYPE_PURGE, "Purge"),
        (AUDIT_TYPE_RESTORE, "Restore"),
        (AUDIT_TYPE_READ, "Read"),
        (AUDIT_TYPE_LOGIN, "Log In"),
        (AUDIT_TYPE_LOGOUT, "Log Out"),
        (AUDIT_TYPE_EVENT, "Event"),
        (AUDIT_TYPE_ATTACH, "Attach"),
        (AUDIT_TYPE_NOTIFY, "Notify"),
        (AUDIT_TYPE_DELIVERED, "Delivery"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, null=False, blank=False, choices=AUDIT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        db_index=True,
        related_name="created_by",
        on_delete=models.PROTECT,
    )
    assisted_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        db_index=True,
        related_name="assisted_by",
        on_delete=models.PROTECT,
    )
    case_id = models.UUIDField(null=True, blank=True, db_index=True)
    model_id = models.UUIDField(null=True, blank=True, db_index=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    milestone = models.BooleanField(default=False)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    data: dict = fields.JSONField(null=True, blank=True)

    def _case_title(self):
        if not self.data:
            self.data = {}
        if "case_title" not in self.data:
            self.data["case_title"] = f"{self.case}" if self.case else ""
        return self.data["case_title"]

    case_title = property(_case_title)

    def __str__(self):
        content_type = self.content_type.model if self.content_type else ""
        created_at_str = self.created_at.isoformat() if self.created_at else ""
        if self.assisted_by:
            return (
                f"{created_at_str}: {self.created_by}" f"{self.type}-{content_type}:{self.model_id}"
            )
        else:
            return (
                f"{created_at_str}: {self.created_by} assisted by {self.assisted_by}:"
                f"{self.type}-{content_type}:{self.model_id}"
            )

    @property
    def case(self):
        from cases.models import Case

        try:
            return Case.objects.get_case(id=self.case_id)
        except Case.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        """Save model override.

        Ensures precomputed properties are populated, serialises `data` json
        field and invokes base implementation.
        """
        self.case_title  # noqa
        self.serialise_data()
        super().save(*args, **kwargs)

    def get_model(self):
        """
        Return the model this audit item relates to
        """
        if self.content_type and self.model_id:
            return self.content_type.get_object_for_this_type(id=self.model_id)
        return None

    def humanise(self):
        return LogHumaniser(self, separator="\n").humanise()

    def to_dict(self):
        return {
            "id": str(self.id),
            "type": self.type,
            "case_id": str(self.case_id),
            "created_at": self.created_at,
            "created_by": {"id": str(self.created_by.id), "user": self.created_by.email}
            if self.created_by
            else {"id": None, "user": None},
            "assisted_by": {"id": str(self.assisted_by.id), "user": self.assisted_by.email}
            if self.assisted_by
            else {"id": None, "user": None},
            "model_id": str(self.model_id) if self.model_id else None,
            "content_type": self.content_type.model if self.content_type else None,
            "milestone": str(self.milestone),
            "data": self.data,
            "humanised": self.humanise(),
        }

    @staticmethod
    def row_columns():
        """Get model column names.

        Get model column names for reporting purposes.
        :returns (list): A list of column names.
        """
        return [
            "Audit ID",
            "Audit Type",
            "Created At",
            "Created By",
            "Assisted By",
            "Case Id",
            "Case",
            "Record Id",
            "Record Type",
            "Audit Content",
            "Change Data",
        ]

    def row_values(self):
        """Get model row values.

        Get model column values for reporting purposes.
        :returns (list): A list of row values.
        """
        row_data = self.to_dict()
        return [
            row_data.get("id"),
            row_data.get("type"),
            row_data.get("created_at", datetime.datetime.min).strftime(
                settings.API_DATETIME_FORMAT
            ),
            row_data.get("created_by").get("email"),
            row_data.get("assisted_by").get("email"),
            row_data.get("case_id"),
            self.case_title,
            row_data.get("model_id"),
            row_data.get("content_type"),
            row_data.get("humanised"),
            json.dumps(row_data.get("data")),
        ]

    def to_row(self):
        """Get row.

        :returns (list): Returns a list of tuples representing a row, each
            tuple is a column name and column value i.e.
            [(column, value), (column, value)...]
        """
        columns = self.row_columns()
        values = self.row_values()
        merged = map(lambda i: (columns[i], values[i]), range(len(columns)))
        return [item for item in merged]

    def serialise_data(self):
        if self.data:
            for key, value in self.data.items():
                if hasattr(value, "to_dict"):
                    self.data[key] = value.to_dict()  # noqa
                elif value and not isinstance(value, (str, int, dict, list)):
                    self.data[key] = str(value)
                else:
                    self.data[key] = value


class LogHumaniser:
    def __init__(self, audit, separator=None):
        self.separator = separator or ""
        self.audit = audit
        self.data = audit.data or {}
        self.has_message = self.data.get("message")
        self.type = audit.type
        self.message = []

    def humanise(self):
        try:
            if self.has_message:
                self.message.append(self.data["message"])
            sub_func = f"humanise_{self.type.lower()}"
            if hasattr(self, sub_func):
                self.message.append(getattr(self, sub_func)())
            return self.separator.join(self.message)
        except Exception as exc:
            return f"Error humanising audit content: {exc} {self.data}"

    def humanise_attach(self):
        if self.data.get("id"):
            return f"Attached to {self.audit.content_type} id {self.data.get('id','unknown')}"
        return ""

    def humanise_update(self):
        return self.humanise_diff()

    def humanise_create(self):
        if self.data.get("id"):
            try:
                model = self.audit.get_model()
                return f"Created: {model}"
            except ObjectDoesNotExist:
                return f"Created ID: {self.data.get('id','unknown id')}"
        return ""

    def humanise_delete(self):
        if self.data.get("id"):
            return f"Deleted ID: {self.data.get('id','unknown id')}"
        return ""

    @staticmethod
    def limit_chars(text, limit=None):
        limit = limit or 25
        text = str(text)
        if text and len(text) > limit:
            return f"{text[:limit]}..."
        return text

    def humanise_diff(self):
        diff = []
        for key, spec in self.data.items():
            if isinstance(spec, dict) and "to" in spec and "from" in spec:
                to_text = self.limit_chars(extract_text(spec["to"]))
                diff.append(
                    f"{key} changed from `{extract_text(spec['from']) or 'empty value'}` "
                    f"to `{to_text}`."
                )
        return self.separator.join(diff)
