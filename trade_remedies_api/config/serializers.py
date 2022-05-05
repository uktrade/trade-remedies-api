from collections import OrderedDict
from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import MISSING_ERROR_MESSAGE, SkipField, empty, get_error_detail, \
    set_value
from rest_framework.serializers import as_serializer_error
from rest_framework.settings import api_settings

from core.exceptions import CustomValidationError, CustomValidationErrors


class BaseSerializer(serializers.Serializer):
    @property
    def data(self):
        return {"result": super().data}


class BaseModelSerializer(BaseSerializer, serializers.ModelSerializer):
    pass


class CustomValidationSerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_list = {}

    def to_internal_value(self, data):
        """
        Dict of native values <- Dict of primitive datatypes.
        """
        if not isinstance(data, Mapping):
            message = self.error_messages['invalid'].format(
                datatype=type(data).__name__
            )
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            }, code='invalid')

        ret = OrderedDict()
        errors = OrderedDict()
        fields = self._writable_fields

        for field in fields:
            validate_method = getattr(self, 'validate_' + field.field_name, None)
            primitive_value = field.get_value(data)
            try:
                validated_value = field.run_validation(primitive_value)
                if validate_method is not None:
                    validated_value = validate_method(validated_value)
            except ValidationError as exc:
                errors[field.field_name] = exc
            except DjangoValidationError as exc:
                errors[field.field_name] = get_error_detail(exc)
            except SkipField:
                pass
            else:
                set_value(ret, field.source_attrs, validated_value)

        if errors:
            self.error_list.update(errors)
            raise CustomValidationError(error_list=errors)

        return ret

    def run_validation(self, data=empty):
        """
        We override the default `run_validation`, because the validation
        performed by validators and the `.validate()` method should
        be coerced into an error dictionary with a 'non_fields_error' key.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        value = self.to_internal_value(data)
        try:
            self.run_validators(value)
            value = self.validate(value)
            assert value is not None, '.validate() should return the validated data'
        except (ValidationError, DjangoValidationError, CustomValidationError) as exc:
            self.error_list["non_field_errors"] = exc

        if self.error_list:
            raise CustomValidationErrors(error_list=self.error_list)

        return value

    def is_valid(self, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = self.error_list
            else:
                self._errors = {}

        return not bool(self._errors)

    @property
    def errors(self):
        if not hasattr(self, '_errors'):
            msg = 'You must call `.is_valid()` before accessing `.errors`.'
            raise AssertionError(msg)
        return self._errors

    @property
    def data(self):
        return {"result": super().data}


class CustomValidationModelSerializer(CustomValidationSerializer, serializers.ModelSerializer):
    """Raises CustomValidationErrors for use in V2 error handling using a DRF ModelSerializer"""


def custom_fail(self, key, **kwargs):
    """
    A helper method that simply raises a validation error.
    """
    try:
        msg = self.error_messages[key]
    except KeyError:
        class_name = self.__class__.__name__
        msg = MISSING_ERROR_MESSAGE.format(class_name=class_name, key=key)
        raise AssertionError(msg)
    if isinstance(msg, dict):
        # We have passed a dict containing the field, error_text, and error_summary, we want to
        # raise a CustomValidationError here
        raise CustomValidationError(**msg)
    message_string = msg.format(**kwargs)
    raise ValidationError(message_string, code=key)


serializers.Field.fail = custom_fail
