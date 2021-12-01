import json
import pytest


def test_login():
    pass


def test_login_bad_creds():
    pass


def test_login_bad_trusted_token():
    pass


def test_2fa_not_required():
    pass
    # Should get auth token


def test_2fa_required_token_expired():
    pass
    # Should get auth token "withheld"


def test_2fa_required_user_agent_changed():
    pass
    # Should get auth token "withheld"


def test_2fa_required():
    pass


def test_2fa_verify_success():
    pass


def test_2fa_verify_fail():
    pass


def test_2fa_resend():
    pass


def test_email_verify():
    pass  # Test right response for valid email verify code


def test_email_verify_fail():
    pass  # Test right response for invalid email verify code


def test_email_check_available():
    pass


def test_email_check_unavailable():
    pass


@pytest.mark.django_db
def test_user_list(authorised_api_client):
    response = authorised_api_client.get("/api/v2/auth/users/")
    data = json.loads(response.content)


@pytest.mark.django_db
def test_user_list_unauthorised(unauthorised_api_client):
    response = unauthorised_api_client.get("/api/v2/auth/users/")
    data = json.loads(response.content)
    # assert data["detail"] == "Authentication credentials were not provided."
