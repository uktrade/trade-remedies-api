import pytest
from authentication.models.email_verification import CODE_LENGTH


pytestmark = pytest.mark.version2


def test_signal_send_verification(fake_user):
    # When a user is created a signal receiver should create and assign
    # an EmailVerification instance then create and send a verification code.
    assert fake_user.email_verification.sent_at
    assert fake_user.email_verification.code
    assert len(fake_user.email_verification.code) == CODE_LENGTH
    # TODO-TRV2 need to mock `notification.send` in EmailVerification.send
    #  and check it's invoked.
