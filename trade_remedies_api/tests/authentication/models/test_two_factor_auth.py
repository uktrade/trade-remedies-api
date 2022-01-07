import datetime

import pytest

from django.conf import settings as django_settings
from django.utils import timezone

from authentication.models import TwoFactorAuth
from authentication.models.two_factor_auth import TwoFactorAuthLocked


pytestmark = pytest.mark.version2


@pytest.fixture
def no_2fa_setting(settings):
    """Override TWO_FACTOR_AUTH_REQUIRED=False."""
    settings.TWO_FACTOR_AUTH_REQUIRED = False


@pytest.fixture
def valid_days_2fa_setting(settings):
    """Override TWO_FACTOR_AUTH_VALID_DAYS=2."""
    settings.TWO_FACTOR_AUTH_VALID_DAYS = 2


@pytest.fixture
def max_attempts(settings):
    """Override TWO_FACTOR_MAX_ATTEMPTS=1."""
    settings.TWO_FACTOR_MAX_ATTEMPTS = 1


@pytest.fixture
def lock_minutes(settings):
    """Override TWO_FACTOR_LOCK_MINUTES=2."""
    settings.TWO_FACTOR_LOCK_MINUTES = 2


def test_2fa_required(fake_user):
    # 2fa is required out of the box.
    assert django_settings.TWO_FACTOR_AUTH_REQUIRED
    assert fake_user.two_factor
    assert fake_user.two_factor.required(user_agent="chrome")


def test_2fa_required_token_expired(fake_user, valid_days_2fa_setting):
    # 2fa is required if validated_at is older than TWO_FACTOR_AUTH_VALID_DAYS.
    assert django_settings.TWO_FACTOR_AUTH_VALID_DAYS == 2
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    fake_user.two_factor.validated_at = three_days_ago
    assert fake_user.two_factor.required(user_agent="chrome")


def test_2fa_required_user_agent_changed(fake_user):
    # 2fa is required if user agent has changed.
    fake_user.two_factor.last_user_agent = "chrome"
    assert fake_user.two_factor.required(user_agent="opera")


def test_2fa_not_required_token_valid(fake_user):
    # 2fa is NOT required if user_agent same and validated_at is less
    # than TWO_FACTOR_AUTH_VALID_DAYS.
    fake_user.two_factor.last_user_agent = "chrome"
    one_day_ago = timezone.now() - datetime.timedelta(days=1)
    fake_user.two_factor.validated_at = one_day_ago
    assert not fake_user.two_factor.required(user_agent="chrome")


def test_2fa_not_required_setting_off(fake_user, no_2fa_setting):
    # 2fa is NOT required if TWO_FACTOR_AUTH_REQUIRED is False,
    # regardless of user_agent same and validated_at.
    assert not django_settings.TWO_FACTOR_AUTH_REQUIRED
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    fake_user.two_factor.validated_at = three_days_ago
    fake_user.two_factor.last_user_agent = "chrome"
    assert not django_settings.TWO_FACTOR_AUTH_REQUIRED
    assert not fake_user.two_factor.required(user_agent="opera")


def test_deliver_token(fake_user):
    two_factor = fake_user.two_factor
    assert two_factor.last_user_agent is None
    assert two_factor.validated_at is None
    assert two_factor.token is None
    assert two_factor.generated_at is None
    assert two_factor.required(user_agent="chrome")
    fake_user.two_factor.deliver_token("chrome")
    two_factor = TwoFactorAuth.objects.get(user=fake_user)
    assert two_factor.last_user_agent == "chrome"
    assert two_factor.validated_at is None
    assert two_factor.token is not None
    assert int(two_factor.token) in range(10000, 99999 + 1)
    assert two_factor.generated_at < timezone.now()
    # TODO-TRV2 - requires test to ensure notification delivery request is invoked.


def test_validate_token_success(fake_user):
    fake_user.two_factor.deliver_token("chrome")
    assert fake_user.two_factor.validate_token(fake_user.two_factor.token, "chrome")


def test_validate_token_fail_expired(fake_user, valid_minutes_2fa_token):
    # 2FA validation will fail if the token age > TWO_FACTOR_CODE_XXX_VALID_MINUTES
    # where XXX is the 2FA delivery type.
    assert fake_user.two_factor.delivery_type == TwoFactorAuth.SMS
    two_minutes_ago = timezone.now() - datetime.timedelta(minutes=2)
    fake_user.two_factor.deliver_token("chrome")
    fake_user.two_factor.generated_at = two_minutes_ago
    assert not fake_user.two_factor.validate_token(fake_user.two_factor.token, "chrome")


def test_validate_token_fail_changed(fake_user):
    # 2FA validation will fail if the token is not same as the one sent.
    fake_user.two_factor.deliver_token("chrome")
    assert not fake_user.two_factor.validate_token("wrong-token", "chrome")


def test_validate_token_fail_agent_changed(fake_user):
    # 2FA validation will fail if the user agent has changed since token was sent.
    fake_user.two_factor.deliver_token("chrome")
    assert not fake_user.two_factor.validate_token(fake_user.two_factor.token, "opera")


def test_validate_token_lock(fake_user, max_attempts):
    # 2FA validation will be locked if > TWO_FACTOR_MAX_ATTEMPTS are made.
    assert django_settings.TWO_FACTOR_MAX_ATTEMPTS == 1
    fake_user.two_factor.deliver_token("chrome")
    assert not fake_user.two_factor.validate_token("wrong-token", "chrome")
    assert fake_user.two_factor.attempts == 1
    assert fake_user.two_factor.locked_until is None
    assert not fake_user.two_factor.validate_token("wrong-token", "chrome")
    assert fake_user.two_factor.attempts == 2
    assert fake_user.two_factor.locked_until is not None
    with pytest.raises(TwoFactorAuthLocked):
        fake_user.two_factor.validate_token("wrong-token", "chrome")


def test_validate_token_unlock(fake_user, max_attempts):
    # 2FA validation will be unlocked after TWO_FACTOR_LOCK_MINUTES.
    assert django_settings.TWO_FACTOR_MAX_ATTEMPTS == 1
    fake_user.two_factor.deliver_token("chrome")
    fake_user.two_factor.validate_token("wrong-token", "chrome")
    fake_user.two_factor.validate_token("wrong-token", "chrome")
    with pytest.raises(TwoFactorAuthLocked):
        fake_user.two_factor.validate_token("wrong-token", "chrome")
    fake_user.two_factor.locked_until = timezone.now() - datetime.timedelta(seconds=1)
    assert fake_user.two_factor.validate_token(fake_user.two_factor.token, "chrome")


def test_str(fake_user):
    assert str(fake_user.two_factor) == "test@example.com last validated at None"  # /PS-IGNORE
