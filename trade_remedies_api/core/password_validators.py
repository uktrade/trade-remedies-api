import string
from django.core.exceptions import ValidationError


class UpperAndLowerCase:
    def validate(self, password, user=None):
        mixed = any(letter.islower() for letter in password) and any(
            letter.isupper() for letter in password
        )
        if not mixed:
            raise ValidationError(
                "Password must include both upper and lower case characters", code="no_mixed_case",
            )

    def get_help_text(self):
        return "Your password must contain both upper and lower case characters"


class ContainsSpecialChar:
    def validate(self, password, user=None):
        special_chars = string.punctuation
        if not any([char in password for char in special_chars]):
            raise ValidationError(
                f"Password must include at least one special character ({special_chars})",
                code="no_special_char",
            )

    def get_help_text(self):
        return f"Your password must contain at least one special character ({string.punctuation})"
