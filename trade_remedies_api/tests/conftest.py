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
    return user


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
    monkeypatch.setattr(auth_token_serializers, "authenticate", mocker.Mock())
