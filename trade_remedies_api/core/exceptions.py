from collections import defaultdict

from rest_framework.exceptions import APIException
from rest_framework import serializers, status

from core.validation_errors import validation_errors


class UserExists(Exception):
    message = "This user already exists"


class ValidationAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, serializer_errors, *args, **kwargs):
        self.serializer_errors = serializer_errors
        super().__init__(*args, **kwargs)
        self.detail = defaultdict(list)
        for field, error in self.serializer_errors.items():
            if isinstance(error, CustomValidationError):
                self.detail["error_summaries"].append(error.error_summary)
                self.detail[field].append(error.error_text)
            else:
                if isinstance(error.detail, list):
                    # Getting the last element as the first element is the field
                    self.detail[field].append(error.detail[-1])
                else:
                    self.detail[field].append(error.detail)


class CustomValidationErrors(serializers.ValidationError):
    def __init__(self, error_list, *args, **kwargs):
        self.error_list = error_list
        super().__init__(*args, **kwargs)


class CustomValidationError(serializers.ValidationError):
    def __new__(cls, error_list=None, *args, **kwargs):
        if error_list:
            return CustomValidationErrors(error_list=error_list)
        else:
            return super().__new__(cls, *args, **kwargs)

    def __init__(
            self,
            field=None,
            error_summary=None,
            error_text=None,
            error_key=None,
            additional_information=None
    ):
        super().__init__()
        if error_key:
            self.error_key = error_key
            try:
                validation_error = validation_errors[error_key]
            except KeyError:
                #todo - raise to sentry
                self.error_summary = "An unexpected error has occurred"
            else:
                self.field = validation_error.get("field", None)
                self.error_summary = validation_error.get("error_summary", None)
                self.error_text = validation_error.get("error_text", None)
        else:
            self.field = field
            self.error_summary = error_summary
            self.error_text = error_text
            self.error_key = error_key
            self.additional_information = additional_information


class SingleValidationAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, validation_error: CustomValidationError, *args, **kwargs):
        super().__init__(*args, **kwargs)
        detail = defaultdict(list)
        if validation_error.error_summary:
            detail["error_summaries"].append(validation_error.error_summary)
        if validation_error.error_text:
            detail[validation_error.field].append(validation_error.error_text)
        if validation_error.error_key:
            detail["error_keys"] = validation_error.error_key
        if validation_error.additional_information:
            detail["additional_information"] = validation_error.additional_information
        self.detail = dict(detail)


class TwoFactorRequestedTooMany(Exception):
    """TwoFactor code could not be generated as it was generated too recently in the past"""
