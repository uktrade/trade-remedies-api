from authentication.models import TwoFactorAuth


def check_locked(fake_user):
    assert fake_user.two_factor


def test_2fa_required():
    pass


def test_deliver_token():
    pass


def test_validate_token_success():
    pass


def test_validate_token_fail():
    pass


def test_validate_token_lock():
    pass
