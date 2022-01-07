import pytest

from conftest import do_post


pytestmark = [pytest.mark.version2, pytest.mark.functional]


def test_username_available(fake_user, unauthorised_api_client, trusted_token, actual_user_data):
    # Given a valid username and a trusted token, query the availability of the
    # username.
    response = do_post(unauthorised_api_client, actual_user_data, "/api/v2/auth/email-availability/")
    assert response.status_code == 200
    assert not response.json()["available"]


def test_username_unavailable(fake_user, unauthorised_api_client, trusted_token, anon_user_data):
    # Given an invalid username and a trusted token, query the availability of the
    # username.
    response = do_post(unauthorised_api_client, anon_user_data, "/api/v2/auth/email-availability/")
    assert response.status_code == 200
    assert response.json()["available"]
