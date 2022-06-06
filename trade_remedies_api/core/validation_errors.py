from config.settings.base import env

validation_errors = {
    "wrong_email_password_combination": {
        "field": "email",
        "error_text": "Enter the correct email address and password combination",
        "error_summary": "The email address or password is incorrect",
    },
    "incorrect_timeout": {
        "error_text": "You have entered incorrect sign in details too many time and your account will be locked for [xx] minutes"
    },
    "password_fails_requirements": {
        "field": "password",
        "error_text": "Enter a password that contains 8 or more characters, at least one lowercase letter, at least one capital letter, at least one number and at least one special character for example  !@#$%^&",
        "error_summary": "The password is not using the correct format",
    },
    "password_upper_lower_case": {
        "field": "password",
        "error_text": "Password must include both upper and lower case characters",
    },
    "password_required": {
        "field": "password",
        "error_summary": "You need to enter your password",
        "error_text": "Enter your password",
    },
    "2fa_code_failed_delivery": {
        "field": "code",
        "error_summary": "The authentication code could not be sent, try again shortly",
    },
    "2fa_code_expired": {
        "field": "code",
        "error_text": "Enter the correct authentication code or request a new code",
        "error_summary": "This authentication code has expired",
    },
    "2fa_code_not_valid": {
        "field": "code",
        "error_text": "Enter a valid authentication code",
        "error_summary": "The authentication code is incorrect",
    },
    "2fa_requested_too_many_times": {
        "field": "code",
        "error_summary": "Please wait %s seconds before requesting another authentication code",
    },
    "email_not_valid": {
        "field": "email",
        "error_text": "Enter your email address in the correct format. Eg. name@example.com",  # /PS-IGNORE
        "error_summary": "Your email address needs to be in the correct format. Eg. name@example.com",  # /PS-IGNORE
    },
    "email_required": {
        "field": "email",
        "error_text": "Enter your email address. Eg. name@example.com",  # /PS-IGNORE
        "error_summary": "Enter your email address",
    },
    "2fa_code_required": {
        "field": "code",
        "error_text": "Enter the correct authentication code or request a new code",
        "error_summary": "You need to enter an authentication code",
    },
    "2fa_code_locked": {
        "field": "code",
        "error_text": "The authentication code is incorrect and your account has been temporarily locked. Try again in 5 minutes",
        "error_summary": "The authentication code is incorrect and your account has been temporarily locked. Try again in 5 minutes",
    },
    "login_incorrect_timeout": {
        "error_summary": f"You have entered incorrect sign in details too many times and your account will be locked for {env('FAILED_LOGIN_COOLOFF', default=10)} minutes"
    },
    "invalid_access": {"error_summary": "Invalid access to environment"},
}
