import pytest

from conftest import do_post


pytestmark = [pytest.mark.version2, pytest.mark.functional, pytest.mark.django_db]


def test_email_verify(fake_user, authorised_api_client):
    response = do_post(authorised_api_client, {}, f"/api/v2/auth/verify/code/{fake_user.email_verification.code}/")
    assert response.status_code == 200
    assert response.json()["verified"]


def test_email_verify_fail(authorised_api_client):
    response = do_post(authorised_api_client, {}, "/api/v2/auth/verify/code/not-a-valid-code/")
    assert response.status_code == 400


def test_verify_resend(authorised_api_client):
    response = do_post(authorised_api_client, {}, "/api/v2/auth/verify/resend/")
    assert response.status_code == 200
    assert response.json()["verification-code-resent"]
