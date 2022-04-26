from django.utils.translation import gettext_lazy as _

validation_errors = {
    "wrong_email_password_combination": {
        "field": "email",
        "error_text": _("Enter the correct email address and password combination"),
        "error_summary": _("The email address or password is incorrect")
    },
    "incorrect_timeout": {
        "error_text": _(
            "You have entered incorrect sign in details too many time and your account will be locked for [xx] minutes")
    },
    "password_fails_requirements": {
        "field": "password",
        "error_text": "Enter a password that contains 8 or more characters, at least one lowercase letter, at least one capital letter, at least one number and at least one special character for example  !@#$%^&",
        "error_summary": "The password is not using the correct format"
    },
    "password_upper_lower_case": {
        "field": "password",
        "error_text": "Password must include both upper and lower case characters",
    },
    "two_code_failed_delivery": {
        "field": "2fa_code",
        "error_text": "The code could not be sent. Please retry in 2 minutes",
        "error_summary": "The authentication code could not be sent",
    }

}
