import datetime
import uuid

import pytz
from django.db import models
from django.db.models.signals import post_save, post_delete

from audit.utils import audit_log


class AuditableMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        post_save.connect(
            AuditableMixin._audit_upsert,
            sender=self.__class__,
            dispatch_uid="{name}-AuditableMixin-upsert".format(name=self.__class__.__name__),
        )
        post_delete.connect(
            AuditableMixin._audit_purge,
            sender=self.__class__,
            dispatch_uid="{name}-AuditableMixin-delete".format(name=self.__class__.__name__),
        )

    def extract_case(self):
        case = None
        if self.__class__.__name__ == "Case":
            case = self
        elif hasattr(self, "case"):
            case = self.case
        elif hasattr(self, "submission"):
            case = self.submission.case
        elif hasattr(self, "_case_context"):
            case = self._case_context
        return case

    def format_diff_map(self, changes):
        """
        Format a diff struct describing what fields have changed
        in the model and the change form/to.

        The diff data looks like:

            { 'name': {'from': 'Ariel Malka', 'to': 'Harel Malka' } }

        If the change is in a list item, the key would contain the index of the field.
        For example, if list item "categories" had item 1 changed from "Hot" to "Cold",
        it would reflect as:

            {'categories-1': {'from': 'Hot', 'to': 'Cold'}}

        :param the changes to the model:
        :return the standard diff format:
        """
        diff = {}
        exclude_fields = {"created_at", "last_modified", "created_by"}
        for key in set(changes.keys()) - exclude_fields:
            _from_value = self._normalise_diff_value(changes[key])
            _to_value = self._normalise_diff_value(getattr(self, key))
            diff[key] = {"from": _from_value, "to": _to_value}
        return diff

    def _normalise_diff_value(self, value):  # noqa: C901
        """
        Normalise a date/time field to its isoformat when its destined for a json/diff field.
        :param value: the value to normalise
        :return: The value as is, or if its a date/time return its isoformat.
        """
        if type(value) in (datetime.datetime, datetime.date):
            return value.isoformat()
        elif isinstance(value, pytz.tzfile.DstTzInfo) and hasattr(value, "zone"):
            return value.zone
        elif isinstance(value, list):
            return list(map(str, value))
        elif isinstance(value, models.fields.files.FieldFile):
            return value.name
        elif hasattr(value, "to_embedded_dict"):
            return value.to_embedded_dict()
        elif hasattr(value, "to_dict"):
            return value.to_dict()
        elif isinstance(value, uuid.UUID):
            return str(value)
        elif hasattr(value, "id"):
            _value = {"id": str(value.id)}
            if hasattr(value, "name"):
                _value["name"] = value.name
            return _value
        elif hasattr(value, "code") and hasattr(value, "name"):
            return {"name": value.name, "code": value.code}
        return value

    def _assert_audit_user(self, instance, **kwargs):
        user, assisted_by = None, None
        if hasattr(instance, "_user_context") and getattr(instance, "_user_context"):
            user = instance._user_context.user
            assisted_by = instance._user_context.assisted_by
        elif kwargs.get("created") and instance.created_by:
            user = instance.created_by
        return user, assisted_by

    @staticmethod
    def _audit_purge(sender, instance, **kwargs):
        """
        Log purge actions on the model, when a record is permanently removed from the database

        :param sender: The signal sender
        :param instance: The model instance
        :param kwargs: Any additional arguments sent by the signal processor
        """
        audit_type = "PURGE"
        created_by, assisted_by = instance._assert_audit_user(instance, **kwargs)
        case = instance.extract_case()
        audit_log(audit_type, created_by, assisted_by, case, instance)

    @staticmethod
    def _audit_upsert(sender, instance, **kwargs):
        """
        Log updates to the object, object creations, soft deletes and restores.

        :param sender: The signal sender
        :param instance: The model instance
        :param kwargs: Any additional arguments sent by the signal processor
        """
        if hasattr(instance, "_disable_audit"):
            return None
        audit_type = "CREATE" if kwargs.get("created") else "UPDATE"
        created_by, assisted_by = instance._assert_audit_user(instance, **kwargs)
        case = instance.extract_case()
        if not kwargs.get("created") and getattr(instance, "get_dirty_fields"):
            dirty_fields = instance.get_dirty_fields(check_relationship=True)
            data = instance.format_diff_map(dirty_fields)
            if "deleted_at" in dirty_fields and dirty_fields["deleted_at"] is None:
                audit_type = "DELETE"
            elif "deleted_at" in dirty_fields and dirty_fields["deleted_at"]:
                audit_type = "RESTORE"
        if audit_type == "CREATE":
            data = {"id": str(instance.id)}
        audit_log(audit_type, created_by, assisted_by, case, instance, data)

    def _generic_audit(self, message, audit_type=None, **kwargs):
        audit_type = audit_type or "EVENT"
        created_by, assisted_by = self._assert_audit_user(self, **kwargs)
        case = self.extract_case()
        data = {"message": message, **kwargs}
        audit_log(audit_type, created_by, assisted_by, case, self, data)
