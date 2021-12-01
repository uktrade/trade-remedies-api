import pytest

import rest_framework.exceptions
from django.conf import settings

import authentication.models as auth_models
import authentication.serializers as auth_serializers


@pytest.fixture
def serializer_data():
    return {
        "trusted_token": settings.ANON_USER_TOKEN,
    }


@pytest.fixture
def valid_2fa_serializer_data(serializer_data):
    serializer_data["two_factor_token"] = "token"
    return serializer_data


@pytest.fixture
def fake_2fa_request(mocker):
    request = mocker.Mock()
    request.META = {"HTTP_X_USER_AGENT": "chrome"}
    request.user = mocker.Mock()
    request.user.two_factor = mocker.Mock()
    return request


@pytest.fixture
def fake_2fa_request_valid(mocker, fake_2fa_request):
    fake_2fa_request.user.two_factor.validate_token = mocker.Mock(return_value=True)
    return fake_2fa_request


@pytest.fixture
def fake_2fa_request_invalid(mocker, fake_2fa_request):
    fake_2fa_request.user.two_factor.validate_token = mocker.Mock(return_value=False)
    return fake_2fa_request


@pytest.fixture
def fake_2fa_request_locked(mocker, fake_2fa_request):
    fake_2fa_request.user.two_factor.validate_token = mocker.Mock(
        side_effect=auth_serializers.TwoFactorAuthLocked
    )
    return fake_2fa_request


def test_trusted_auth_token_serializer(fake_auth_backend):
    serializer = auth_serializers.TrustedAuthTokenSerializer(
        data={
            "username": "foo",
            "password": "bar",
            "trusted_token": settings.ANON_USER_TOKEN
        }
    )
    assert serializer.is_valid(raise_exception=True)


def test_trusted_auth_token_serializer_no_data():
    serializer = auth_serializers.TrustedAuthTokenSerializer(data={})
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "This field is required." in str(e)


def test_trusted_auth_token_serializer_invalid_token():
    data = {
        "username": "foo",
        "password": "bar",
        "trusted_token": None,
    }
    serializer = auth_serializers.TrustedAuthTokenSerializer(data=data)
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "This field may not be null." in str(e)

    data["trusted_token"] = "not-a-token"
    serializer = auth_serializers.TrustedAuthTokenSerializer(data=data)
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "Unable to fulfil request without a valid trusted token." in str(e)


def test_two_factor_token_serializer(fake_2fa_request_valid, valid_2fa_serializer_data):
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request_valid}
    )
    assert serializer.is_valid(raise_exception=True)


def test_two_factor_token_serializer_no_data(fake_2fa_request_valid):
    serializer = auth_serializers.TwoFactorTokenSerializer(data={})
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'trusted_token': [ErrorDetail(string='This field is required." in str(e)
    assert "'two_factor_token': [ErrorDetail(string='This field is required." in str(e)


def test_two_factor_token_serializer_no_trusted_token(fake_2fa_request_valid):
    data = {
        "two_factor_token": "token",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request_valid}
    )
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'trusted_token': [ErrorDetail(string='This field is required." in str(e)
    assert "'two_factor_token': [ErrorDetail(string='This field is required." not in str(e)


def test_two_factor_token_serializer_no_2fa_token(fake_2fa_request_valid):
    data = {
        "trusted_token": "not-a-token",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request_valid}
    )
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'trusted_token': [ErrorDetail(string='This field is required." not in str(e)
    assert "'two_factor_token': [ErrorDetail(string='This field is required." in str(e)


def test_two_factor_token_serializer_invalid_trusted_token(fake_2fa_request_valid):
    data = {
        "two_factor_token": "token",
        "trusted_token": "not-a-token",
    }
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=data,
        context={'request': fake_2fa_request_valid}
    )
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "Unable to fulfil request without a valid trusted token." in str(e)


def test_two_factor_token_serializer_invalid_2fa_token(
        fake_2fa_request_invalid,
        valid_2fa_serializer_data
):
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request_invalid}
    )
    with pytest.raises(auth_serializers.Invalid2FAToken) as e:
        serializer.is_valid(raise_exception=True)
    assert "Two factor token is invalid." in str(e.value)


def test_two_factor_token_serializer_too_many_attempts(
        fake_2fa_request_locked,
        valid_2fa_serializer_data
):
    serializer = auth_serializers.TwoFactorTokenSerializer(
        data=valid_2fa_serializer_data,
        context={'request': fake_2fa_request_locked}
    )
    with pytest.raises(auth_serializers.TooManyAttempts) as e:
        serializer.is_valid(raise_exception=True)
    assert "Too many two factor authentication attempts" in str(e.value)


def test_email_availability_serializer(serializer_data):
    data = serializer_data
    data["email"] = "test@example.com"  # /PS-IGNORE
    serializer = auth_serializers.EmailAvailabilitySerializer(data=data)
    assert serializer.is_valid()


def test_email_availability_serializer_no_email(serializer_data):
    data = serializer_data
    serializer = auth_serializers.EmailAvailabilitySerializer(data=data)
    with pytest.raises(rest_framework.exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "'email': [ErrorDetail(string='This field is required." in str(e)


def test_user_serializer(fake_user):
    queryset = auth_models.User.objects.all()
    serializer = auth_serializers.UserSerializer(queryset, many=True)
    assert len(serializer.data) == 1
