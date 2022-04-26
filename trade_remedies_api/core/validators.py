import re

from rest_framework.exceptions import ValidationError


class SerializerValidationError:
    def __init__(self, error_text, error_id=None, field=None):
        super().__init__()
        self.error_text = error_text
        self.error_id = error_id
        self.field = field or '__all__'


def email_validator(value):
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not re.search(email_regex, value) or not value:
        raise ValidationError(
            "Enter an email address in the correct format, like name@example.com"
        )
