import pytest


def do_post(client, data, url, user_agent="chrome"):
    return client.post(
        url,
        data=data,
        format="json",
        HTTP_X_USER_AGENT=user_agent,
    )


def do_login(client, data, user_agent="chrome"):
    return do_post(client, data, "/api/v2/auth/login/", user_agent)


def do_2fa(client, data, user_agent="chrome"):
    return do_post(client, data, "/api/v2/auth/two-factor/", user_agent)


def set_creds(client, token):
    client.credentials(HTTP_AUTHORIZATION="Bearer " + token)


@pytest.fixture
def login_data(actual_user_data):
    actual_user_data["password"] = "test1234"
    return actual_user_data


@pytest.fixture
def two_factor_data(fake_user, actual_user_data):
    actual_user_data["two_factor_token"] = fake_user.two_factor.token
    return actual_user_data
