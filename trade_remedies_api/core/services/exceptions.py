"""
Custom API exceptions
"""

from rest_framework.exceptions import APIException, ValidationError
from rest_framework import status


class NotFoundApiExceptions(APIException):
    status_code = status.HTTP_404_NOT_FOUND


class InvalidRequestParams(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class RequestValidationError(ValidationError):
    status_code = status.HTTP_400_BAD_REQUEST


class IntegrityErrorRequest(APIException):
    """
    Generic integritry error exception
    """

    status_code = status.HTTP_400_BAD_REQUEST


class InvalidFileUpload(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class ServerError(APIException):
    """
    Generic 500 error
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class AccessDenied(APIException):
    """
    Login error / user inactive
    """

    status_code = status.HTTP_401_UNAUTHORIZED


class InvalidRequestLockout(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, detail=None, failures=None):
        super().__init__(detail=detail, code=self.status_code)
        self.failures = failures or 0


class NotifyError(APIException):
    pass
