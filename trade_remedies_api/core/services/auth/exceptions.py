from rest_framework.exceptions import ValidationError


class EasyDRFValidationError(ValidationError):
    def __init__(self, detail=None, code=None):
        self.original_detail = detail
        self.original_code = code
        super().__init__(detail, code)
