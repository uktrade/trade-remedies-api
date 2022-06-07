import logging
from collections import defaultdict

from rest_framework.exceptions import APIException
from rest_framework import serializers, status

from core.validation_errors import validation_errors

logger = logging.getLogger(__name__)


class UserExists(Exception):
    message = "This user already exists"


class ValidationAPIException(APIException):
    """Exception raised when a serializer raises a validation error.

    This accepts a dictionary of errors (which serializers will already have), which it then loops
    over and appends to the body of the error response. It accepts dictionaries containing both
    CustomValidationErrors and native DRF ValidationErrors.

    The response body (self.detail) is then parsed by the client for display to the end user.
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, serializer_errors, *args, **kwargs):
        self.serializer_errors = serializer_errors
        super().__init__(*args, **kwargs)
        self.detail = defaultdict(list)
        for field, error in self.serializer_errors.items():
            if isinstance(error, CustomValidationError):
                self.detail["error_summaries"].append((field, error.error_summary))
                if hasattr(error, "error_text"):
                    if isinstance(field, list):
                        # Multiple fields should be highlighted with the same error
                        for each in field:
                            self.detail[each].append(error.error_text)
                    else:
                        self.detail[field].append(error.error_text)
            else:
                # It's a DRF ValidationError
                if isinstance(error.detail, list):
                    # Getting the last element as the first element is the field
                    self.detail[field].append(error.detail[-1])
                else:
                    self.detail[field].append(error.detail)


class CustomValidationErrors(serializers.ValidationError):
    """A wrapper exception for raising multiple CustomValidationError objects."""

    def __init__(self, error_list, *args, **kwargs):
        self.error_list = error_list
        super().__init__(*args, **kwargs)


class CustomValidationError(serializers.ValidationError):
    """Exception raised when a serializer is invalid.

    Arguments:
            field {str} -- The HTML name of the field that this error relates to
            error_summary {str} -- The summary of the error, to be displayed at the top of the page
            error_text {str} -- The error displayed next to the incorrect field
            error_key {str} -- Ease of use, key of this error in the validation_errors.py file
            additional_information {str} -- Pass additional information back to client
    """

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
        additional_information=None,
    ):
        super().__init__()
        if error_key:
            self.error_key = error_key
            try:
                validation_error = validation_errors[error_key]
            except KeyError:
                logging.error(f"Unknown error key {error_key} attempted lookup")
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
