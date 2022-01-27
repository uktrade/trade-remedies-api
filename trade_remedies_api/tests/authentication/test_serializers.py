import pytest

import rest_framework.exceptions
from rest_framework import serializers
from django.conf import settings

import authentication.serializers as auth_serializers


pytestmark = pytest.mark.version2


@pytest.fixture
def serializer_data():
    """Basic serializer data with trusted token."""
    return {
        "trusted_token": settings.ANON_USER_TOKEN,
    }


@pytest.fixture
def fake_2fa_user(monkeypatch, mocker):
    """Fake user performing a 2FA verification."""
    user = mocker.Mock()
    user.username = "username"
    user.two_factor = mocker.Mock()
    user.two_factor.validate_token = mocker.Mock(return_value=True)
    mock_get_user = mocker.Mock(return_value=user)
    monkeypatch.setattr(
        auth_serializers.TwoFactorTokenSerializer,
        "get_user",
        mock_get_user
    )
    return user


@pytest.fixture
def fake_2fa_user_invalid(mocker, fake_2fa_user):
    """Fake user performing a 2FA verification with invalid 2fa check result."""
    fake_2fa_user.two_factor.validate_token = mocker.Mock(return_value=False)
    return fake_2fa_user


@pytest.fixture
def fake_2fa_user_nonexistent(mocker, monkeypatch, fake_2fa_user):
    """Nonexistent user performing a 2FA verification."""
    fake_2fa_user.two_factor.validate_token = mocker.Mock(
        side_effect=serializers.ValidationError)
    return fake_2fa_user


@pytest.fixture
def fake_2fa_user_locked(mocker, fake_2fa_user):
    """Fake user performing a 2FA verification with 2fa locked."""
    fake_2fa_user.two_factor.validate_token = mocker.Mock(
        side_effect=auth_serializers.TwoFactorAuthLocked
    )
    return fake_2fa_user


@pytest.fixture
def valid_2fa_serializer_data(serializer_data, fake_2fa_user):
    """Serializer data with trusted token and 2FA token."""
    serializer_data["two_factor_token"] = "token"
    serializer_data["username"] = fake_2fa_user.username
    return serializer_data


def test_trusted_auth_token_serializer(fake_auth_backend):
    # Given a username, password and trusted token, TrustedAuthTokenSerializer
    # is valid.
    serializer = auth_serializers.TrustedAuthTokenSerializer(
        data={
            "username": "foo",
            "password": "bar",
            "trusted_token": settings.ANON_USER_TOKEN
        }
    )
    assert serializer.is_valid(raise_exception=True)


def test_trusted_auth_token_serializer_no_data():
    # Given no data, TrustedAuthTokenSerializer is not valid.
    serializer = auth_serializers.TrustedAuthTokenSerializer(data={})
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "This field is required." in str(e)


def test_trusted_auth_token_serializer_invalid_token():
    # With no trusted token, or an invalid token TrustedAuthTokenSerializer
    # is not valid.
    data = {
        "username": "foo",
        "password": "bar",
        "trusted_token": None,
    }
    serializer = auth_serializers.TrustedAuthTokenSerializer(data=data)
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "This field may not be null." in str(e)

    data["trusted_token"] = "not-a-token"
    serializer = auth_serializers.TrustedAuthTokenSerializer(data=data)
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "Unable to fulfil request without a valid trusted token." in str(e)


def test_two_factor_token_serializer(
        fake_2fa_request,
        fake_2fa_user,
        valid_2fa_serializer_data
):
    # Given a username and trusted token, TwoFactorTokenSerializer is valid.
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request}
    )
    assert serializer.is_valid(raise_exception=True)


def test_two_factor_token_serializer_no_data(fake_2fa_request):
    # Given no data, TwoFactorTokenSerializer is not valid.
    serializer = auth_serializers.TwoFactorTokenSerializer(data={})
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'trusted_token': [Error" in str(e)
    assert "'two_factor_token': [Error" in str(e)
    assert "'username': [Error" in str(e)


def test_two_factor_token_serializer_no_trusted_token(fake_2fa_request, fake_2fa_user):
    # With no trusted token, TwoFactorTokenSerializer is not valid.
    data = {
        "two_factor_token": "token",
        "username": "username",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'trusted_token': [Error" in str(e)


def test_two_factor_token_serializer_invalid_trusted_token(fake_2fa_request, fake_2fa_user):
    # With invalid trusted token, TwoFactorTokenSerializer is not valid.
    data = {
        "two_factor_token": "token",
        "trusted_token": "not-a-token",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "Unable to fulfil request without a valid trusted token." in str(e)


def test_two_factor_token_serializer_no_2fa_token(fake_2fa_request, fake_2fa_user):
    # With no 2fa token, TwoFactorTokenSerializer is not valid.
    data = {
        "trusted_token": "token",
        "username": "username",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'two_factor_token': [Error" in str(e)


def test_two_factor_token_serializer_invalid_2fa_token(
        fake_2fa_request,
        fake_2fa_user_invalid,
        valid_2fa_serializer_data
):
    # With invalid 2fa token, TwoFactorTokenSerializer is not valid.
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(auth_serializers.Invalid2FAToken) as e:
        serializer.is_valid(raise_exception=True)
    assert "Two factor token is invalid." in str(e.value)


def test_two_factor_token_serializer_too_many_attempts(
        fake_2fa_request,
        fake_2fa_user_locked,
        valid_2fa_serializer_data
):
    # With 2fa locked, TwoFactorTokenSerializer is not valid.
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(auth_serializers.TooManyAttempts) as e:
        serializer.is_valid(raise_exception=True)
    assert "Too many two factor authentication attempts" in str(e.value)


def test_two_factor_token_serializer_nonexistent_user(
        fake_2fa_request,
        fake_2fa_user_nonexistent,
        valid_2fa_serializer_data
):
    # With nonexistent user, TwoFactorTokenSerializer is not valid.
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request}
    )
    with pytest.raises(serializers.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
