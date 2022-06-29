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
        "error_summary": "Your password needs to contain the correct characters",
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
    "wrong_email_verification_code": {"error_summary": "Invalid access to environment"},
    "no_name_entered": {
        "field": "name",
        "error_text": "Enter your name",
        "error_summary": "You need to enter your name",
    },
    "no_email_entered": {
        "field": "email",
        "error_text": "Enter your email address",
        "error_summary": "You need to enter your email address",
    },
    "terms_and_conditions_not_accepted": {
        "field": "terms_and_conditions_accept",
        "error_text": "Select if you have read and understood the Terms of Use and Privacy Notice",
        "error_summary": "Agree to the Terms of Use and Privacy Notice to create your account",
    },
    "no_password_entered": {
        "field": "password",
        "error_text": "Enter your password",
        "error_summary": "You need to enter your password",
    },
    "no_two_factor_selected": {
        "field": "two_factor_choice",
        "error_text": "Choose mobile or email",
        "error_summary": "Choose how to complete two-factor authentication",
    },
    "no_country_selected": {
        "field": "mobile_country_code",
        "error_text": "Select your country code",
        "error_summary": "Select the country code for your mobile number",
    },
    "invalid_mobile_number": {
        "field": "mobile",
        "error_text": "Enter a mobile number using digits only and without using the characters  () or -",
        "error_summary": "Your mobile number needs to be entered in the correct format",
    },
    "no_mobile_entered": {
        "field": "mobile",
        "error_text": "Enter your mobile number",
        "error_summary": "You need to enter your mobile number",
    },
    "organisation_registered_country_not_selected": {
        "field": "uk_employer",
        "error_text": "Select Yes or No",
        "error_summary": "You need to select if your organisation is a UK registered company",
    },
    "companies_house_not_searched": {
        "field": "uk_employer",
        "error_text": "Enter your company name or company number",
        "error_summary": "You need to enter your registered company name or company number",
    },
    "companies_house_not_selected": {
        "field": "input-autocomplete",
        "error_text": "Select your company",
        "error_summary": "Select your company",
    },
    "no_company_name_entered": {
        "field": "organisation_name",
        "error_text": "Enter the name of your organisation",
        "error_summary": "We need the name of your organisation",
    },
    "no_company_post_code_or_number_entered": {
        "field": ["address", "post_code"],
        "error_text": "Enter either your organisation's registration number or the postcode for your organisation's address",
        "error_summary": "We need either your organisation's registration number or the postcode for your organisation's address",
    },
    "no_company_address_entered": {
        "field": "address",
        "error_text": "Enter your organisation's address",
        "error_summary": "We need an address for your organisation",
    },
    "no_company_country_selected": {
        "field": "country",
        "error_text": "Select your country",
        "error_summary": "Select the country for your organisation",
    },
    "incorrect_vat_format": {
        "field": "company_vat_number",
        "error_summary": "You have entered an incorrect VAT number",
    },
    "incorrect_eori_format": {
        "field": "company_eori_number",
        "error_summary": "You have entered an incorrect EORI number",
    },
    "incorrect_duns_format": {
        "field": "company_duns_number",
        "error_text": "Enter your D‑U‑N‑S Number using 9 digits",
        "error_summary": "You have entered an incorrect D‑U‑N‑S Number",
    },
    "incorrect_url": {
        "field": "company_website",
        "error_text": "Enter the correct web address",
        "error_summary": "The website address you have entered does not look valid",
    },
}
