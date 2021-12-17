"""Test Fixtures.

Global `pytest` fixtures for Trade Remedies API V2.
"""
import pytest

from rest_framework.authtoken.models import Token
from rest_framework.authtoken import serializers as auth_token_serializers
from rest_framework.test import APIClient

from authentication.models.user import User


@pytest.fixture
def fake_user(db):
    """Create a fake user.

    Creates a fake Django super user.  Note the `db` fixture we use here
    returns `None` but its inclusion sets up the test database.
    """
    try:
        user = User.objects.get(email="test@example.com")
    except User.DoesNotExist:
        user = User.objects.create_superuser(
            email="test@example.com",
            password="test1234"
        )
        user.is_active = True  # Mimic email verification
        user.save()
        assert user.two_factor
    return user


@pytest.fixture
def trusted_token(settings):
    """Override ANON_USER_TOKEN=test-trusted-token."""
    settings.ANON_USER_TOKEN = "test-trusted-token"


@pytest.fixture
def two_fa_disabled(settings):
    """Override TWO_FACTOR_AUTH_REQUIRED=False."""
    settings.TWO_FACTOR_AUTH_REQUIRED = False


@pytest.fixture
def two_fa_disabled(settings):
    """Override TWO_FACTOR_AUTH_REQUIRED=False."""
    settings.TWO_FACTOR_AUTH_REQUIRED = False


@pytest.fixture
def valid_minutes_2fa_token(settings):
    """Override TWO_FACTOR_CODE_SMS_VALID_MINUTES=1."""
    settings.TWO_FACTOR_CODE_SMS_VALID_MINUTES = 1


@pytest.fixture
def auth_token(fake_user):
    """Auth token for user."""
    token = Token.objects.create(user=fake_user)
    return token.key


@pytest.fixture
def unauthorised_api_client():
    """Un-authorised API Client."""
    client = APIClient()
    return client


@pytest.fixture
def authorised_api_client(unauthorised_api_client, auth_token):
    """Authorised API Client."""
    client = unauthorised_api_client
    client.credentials(HTTP_AUTHORIZATION="Bearer " + auth_token)
    return client


@pytest.fixture
def fake_auth_backend(monkeypatch, mocker):
    """Mocked out backend authenticate method."""
    monkeypatch.setattr(auth_token_serializers, "authenticate", mocker.Mock())


@pytest.fixture
def anon_user_data():
    return {
        "username": "not-a-username",
        "trusted_token": "test-trusted-token",
    }


@pytest.fixture
def actual_user_data(fake_user, anon_user_data):
    anon_user_data["username"] = fake_user.username
    return anon_user_data
