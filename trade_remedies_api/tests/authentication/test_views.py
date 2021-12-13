import datetime
import json
import pytest

from django.utils import timezone

pytestmark = [pytest.mark.version2, pytest.mark.functional]


def do_login(client, data, user_agent="chrome"):
    return client.post(
        "/api/v2/auth/login/",
        data=data,
        format="json",
        HTTP_X_USER_AGENT=user_agent,
    )


def do_2fa(client, data, user_agent="chrome"):
    return client.post(
        "/api/v2/auth/two-factor/",
        data=data,
        format="json",
        HTTP_X_USER_AGENT=user_agent,
    )


def set_creds(client, token):
    client.credentials(HTTP_AUTHORIZATION="Bearer " + token)


@pytest.fixture
def login_data(fake_user):
    return {
        "username": fake_user.username,
        "password": "test1234",
        "trusted_token": "test-trusted-token",
    }


@pytest.fixture
def two_factor_data(fake_user):
    return {
        "username": fake_user.username,
        "two_factor_token": fake_user.two_factor.token,
        "trusted_token": "test-trusted-token",
    }


def test_login_no_2fa(login_data, unauthorised_api_client, trusted_token, two_fa_disabled):
    # If 2FA not required, login as an active user and see in response that 2fa is
    # not required.  See auth token in the response, use auth token in subsequent
    # requests.
    response = do_login(unauthorised_api_client, login_data)
    assert not response.json()["2fa_required"]
    # Can we use token?
    set_creds(unauthorised_api_client, response.json()["token"])
    response = unauthorised_api_client.get("/api/v2/auth/users/")
    assert response.status_code == 200


def test_login_with_2fa(
        fake_user,
        login_data,
        two_factor_data,
        unauthorised_api_client,
        trusted_token
):
    # If 2FA is required, login as an active user and see in response that 2fa is
    # required and that auth token is withheld. Use username and generated 2fa
    # token to perform 2fa step. See auth token in 2fa step response, use auth
    # token in subsequent requests.
    response = do_login(unauthorised_api_client, login_data)
    response_data = response.json()
    assert response_data["token"] == "withheld-pending-2fa"
    assert response_data["2fa_required"]
    fake_user.refresh_from_db()
    two_factor_data["two_factor_token"] = fake_user.two_factor.token
    response = do_2fa(unauthorised_api_client, two_factor_data)
    # Can we use token?
    set_creds(unauthorised_api_client, response.json()["token"])
    response = unauthorised_api_client.get("/api/v2/auth/users/")
    assert response.status_code == 200


def test_login_bad_creds(fake_user, login_data, unauthorised_api_client, trusted_token):
    # Given bad credentials expect 400 Bad Request
    login_data["password"] = "wrong-password"
    assert do_login(unauthorised_api_client, login_data).status_code == 400


def test_login_bad_trusted_token(fake_user, login_data, unauthorised_api_client):
    # Given bad trusted token expect 400 Bad Request
    login_data["trusted_token"] = "not-the-trusted-token"
    assert do_login(unauthorised_api_client, login_data).status_code == 400


def test_2fa_wrong_token(
        fake_user,
        login_data,
        two_factor_data,
        valid_minutes_2fa_token,
        unauthorised_api_client,
        trusted_token
):
    # Given a 2fa token that does not match the one generated, the 2fa response
    # should be 400 Bad Request
    assert do_login(unauthorised_api_client, login_data).status_code == 200
    two_factor_data["two_factor_token"] = "not-the-2fa-token"
    # Post 2fa step with alternate user agent
    response = do_2fa(unauthorised_api_client, two_factor_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Two factor token is invalid."


def test_2fa_token_expired(
        fake_user,
        login_data,
        two_factor_data,
        valid_minutes_2fa_token,
        unauthorised_api_client,
        trusted_token
):
    # Given a 2fa token that's too old, the 2fa response should be
    # 400 Bad Request
    assert do_login(unauthorised_api_client, login_data).status_code == 200
    # Fake an expired token
    fake_user.refresh_from_db()
    two_minutes_ago = timezone.now() - datetime.timedelta(minutes=2)
    fake_user.two_factor.generated_at = two_minutes_ago
    fake_user.two_factor.save()
    # Post 2fa step with expired token
    two_factor_data["two_factor_token"] = fake_user.two_factor.token
    response = do_2fa(unauthorised_api_client, two_factor_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Two factor token is invalid."


def test_2fa_user_agent_changed(
        fake_user,
        login_data,
        two_factor_data,
        valid_minutes_2fa_token,
        unauthorised_api_client,
        trusted_token
):
    # Given a user agent different from login, the 2fa response should be
    # 400 Bad Request
    assert do_login(unauthorised_api_client, login_data).status_code == 200
    fake_user.refresh_from_db()
    two_factor_data["two_factor_token"] = fake_user.two_factor.token
    # Post 2fa step with alternate user agent
    response = do_2fa(unauthorised_api_client, two_factor_data, user_agent="opera")
    assert response.status_code == 400
    assert response.json()["detail"] == "Two factor token is invalid."


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
