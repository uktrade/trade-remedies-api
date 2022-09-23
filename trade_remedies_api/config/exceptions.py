from rest_framework.exceptions import APIException


class InvalidSerializerError(APIException):
    """Trying to save a serializer with invalid data, naughty!"""

    status_code = 400
    default_code = "save_serializer_invalid_error"

    def __init__(self, serializer, detail=None, code=None):
        super().__init__(detail, code)
        self.detail["exception_type"] = self.default_code
        self.detail["serializer_name"] = serializer.__class__.__name__
