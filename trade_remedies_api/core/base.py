import uuid
import json
import re
import types
import datetime
import pytz
from django.db import models
from django.utils import timezone
from django.conf import settings
from django_countries.fields import Country
from audit.mixins import AuditableMixin
from dirtyfields import DirtyFieldsMixin
from django.contrib.contenttypes.models import ContentType
from .user_context import user_context


class SimpleBaseModel(models.Model, DirtyFieldsMixin, AuditableMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
        on_delete=models.SET_NULL,
    )
    modified_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        related_name="%(class)s_modified_by",
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        _user_context = kwargs.pop("user_context", None)
        _case_context = kwargs.pop("case_context", None)
        super().__init__(*args, **kwargs)
        self.set_case_context(_case_context)
        if _user_context:
            self.set_user_context(user_context(_user_context))

    def set_user_context(self, context):
        """
        Set the user context of this model.
        A user context defines the user who is performing the action, and optionally the
        caseworker assisting them by doing the action on their behalf.
        The modified_by (and optionally assisted_by) will be set to the user, and it will be assumed
        the model is now operated on by this user (and/or assisted by the case worker)
        If the user is None, nothing will be changed and current state is maintained.
        """
        self._user_context = user_context(context)

    def set_case_context(self, case):
        """
        Set the case context of this model.
        In cases where the model has no direct association with a case at the point of creation
        or otherwise, there is a conceptual case context (as it is likely it was created in relation
        to a case). In those scenarios it is advised to manually set the case context by calling this
        method. This will ensure that the audit record created is associated with the case it
        related or originated from.
        """
        self._case_context = case

    @property
    def user_context(self):
        try:
            return self._user_context
        except AttributeError:
            return None

    @property
    def case_context(self):
        try:
            return self._case_context
        except AttributeError:
            return None

    def load_attributes(self, data, keys=None, overwrite=True):
        """
        Receive a list of keys, and a dict of properties and loads the valid ones into this model.
        :param attrs: dict of properties
        :param keys: list of keys to load from data. All data keys will be used if not provided
        :param overwrite: boolean. If False, only empty values will be loaded [True]
        :return: a dict of loaded and invalid attributes.
        """
        report = {"set": [], "invalid": []}
        keys = keys or data.keys()
        for key in keys:
            value = data.get(key)
            if key in data and hasattr(self, key):
                data_type = self._meta.get_field(key).__class__.__name__
                if not overwrite and getattr(self, key):
                    continue
                else:
                    if (
                        data_type in ("DateTimeField", "DateField", "UUIDField", "ForeignKey",)
                        and not value
                    ):
                        setattr(self, key, None)
                    else:
                        if data_type == "DateField":
                            value = value[:10]  # chop off any time part
                        try:
                            if data_type == "SmallIntegerField":
                                value = int(value)
                            if data_type == "JSONField":
                                value = json.loads(value)  # to remove escaping
                            setattr(self, key, value)
                        except Exception:
                            print("Invalid field type", key, value, data_type)
                    report["set"].append((key, value))
            else:
                report["invalid"].append((key, value))
        return report

    @property
    def is_new_instance(self):
        """
        Returns True if the instance is new and has yet to be saved to the
        database.
        With a UUID primary key we can not simply check for a `pk` of None.
        """
        return self._state.adding


class BaseModel(SimpleBaseModel):
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        _user_context = kwargs.pop("user_context", None)
        super().__init__(*args, **kwargs)
        if _user_context:
            self.set_user_context(user_context(_user_context))

    def set_user_context(self, context):
        """
        Set the user context of this model.
        A user context defines the user who is performing the action, and optionally the
        caseworker assisting them by doing the action on their behalf.
        The modified_by (and optionally assisted_by) will be set to the user, and it will be assumed
        the model is now operated on by this user (and/or assisted by the case worker)
        If the user is None, nothing will be changed and current state is maintained.
        """
        if context:
            self._user_context = user_context(context)
            if self._user_context:
                self.modified_by = self._user_context.user

    @property
    def user_context(self):
        try:
            return self._user_context
        except AttributeError:
            return None

    def delete(self, purge=False):
        if purge:
            super().delete()
        else:
            self.deleted_at = timezone.now()
            self.save()

    def get_fields(self, **kwargs):
        fields = kwargs.pop("fields", None)
        if fields:
            fields = json.loads(fields) if isinstance(fields, str) else fields
            fields_for_class = fields.get(self.__class__.__name__)
            return fields_for_class

    def to_dict(self, *args, **kwargs):
        """
        Return a JSON ready dict representation of the model.
        If the implementing class has the _to_dict method, it's output
        if used to update the core dict data
        """
        fields = self.get_fields(**kwargs)
        if fields:
            case = kwargs.get("case")
            if case:
                self.set_case_context(case)
            user = kwargs.get("user")
            if user:
                self.set_user_context(user)
            return self.to_json(fields)

        try:
            del kwargs["fields"]
        except:
            pass

        _dict = {
            "id": str(self.id),
            "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
            "last_modified": self.last_modified.strftime(settings.API_DATETIME_FORMAT),
            "created_by": self.created_by.to_embedded_dict() if self.created_by else None,
            "modified_by": self.modified_by.to_embedded_dict() if self.modified_by else None,
        }
        try:
            _dict.update(self._to_dict(*args, **kwargs))
        except AttributeError as ex:
            print("No extended _to_dict:", ex)
            raise
        return _dict

    def to_embedded_dict(self, *args, **kwargs):
        fields = self.get_fields(**kwargs)
        if fields:
            return self.to_json(fields)
        try:
            del kwargs["fields"]
        except:
            pass
        return self._to_embedded_dict(*args, **kwargs)

    def to_minimal_dict(self, *args, **kwargs):
        fields = self.get_fields(**kwargs)
        if fields:
            return self.to_json(fields)
        try:
            del kwargs["fields"]
        except:
            pass
        return self._to_minimal_dict(*args, **kwargs)

    def parse_fields_list(self, fields):
        """
        Parse a field list returning it as a nested dict
        """
        stripped = re.sub(r"\s", "", fields)
        sub = re.sub(r"\w+(?![\[\w])", r'"\g<0>": null', stripped)
        json_str = (
            "{" + re.sub(r"\w+(?=\[)", r'"\g<0>":', sub).replace("[", "{").replace("]", "}") + "}"
        )
        return json.loads(json_str)

    def to_json(self, fields, obj=None, context=None, *args, **kwargs):
        obj = obj or self
        out = {}
        for field, subField in fields.items():
            try:
                if isinstance(obj, dict):
                    val = obj.get(field)
                else:
                    val = getattr(obj, field)
                # If the atribute is a function - run it to get a better val
                if isinstance(val, types.MethodType):
                    val = val()
                if isinstance(val, datetime.datetime):
                    val = val.astimezone(pytz.timezone(settings.TIME_ZONE))
                    val = val.strftime(settings.API_DATETIME_FORMAT)
                elif isinstance(val, datetime.date):
                    val = val.strftime(settings.API_DATE_FORMAT)
                elif isinstance(val, uuid.UUID):
                    val = str(val)
                elif isinstance(val, Country):
                    val = {
                        "name": val.name,
                        "code": val.code,
                    }
                elif isinstance(val, ContentType):
                    val = str(val)
                if subField and isinstance(subField, dict):
                    if hasattr(val, "to_json"):
                        val = val.to_json(fields=subField, context=self)
                    elif val != None:
                        val = self.to_json(fields=subField, obj=val, context=self)
                elif hasattr(val, "to_dict"):
                    val = val.to_dict()
                out[field] = val
            except AttributeError:
                pass
                # if field:
                #    print(f'Field not found "{field}"')
        return out
