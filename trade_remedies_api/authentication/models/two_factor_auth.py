import datetime
import functools
import logging
import random

from django.conf import settings
from django.db import models
from django.utils import timezone


logger = logging.getLogger(__name__)


class TwoFactorAuthLocked(Exception):
    pass


def check_locked(func):
    """Check if 2FA is locked decorator.

    If 2FA is locked raises `TwoFactorAuthLocked`. If lock is expired,
    reset the lock and invoke wrapped method. If not locked at all, just
    invoke wrapped method.
    """
    @functools.wraps(func)
    def _check_locked(self, *args, **kwargs):
        if self.locked_until and timezone.now() < self.locked_until:
            raise TwoFactorAuthLocked()
        elif self.locked_until:
            self.locked_until = None
            self.attempts = 0
        self.save()
        return func(self, *args, **kwargs)
    return _check_locked


class TwoFactorAuth(models.Model):
    """Two Factor Authentication.

    Persists the state of a user's 2FA authentication.
    """
    SMS = "sms"
    EMAIL = "email"
    DELIVERY_TYPE_CHOICES = [
        (SMS, "SMS"),
        (EMAIL, "Email"),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="two_factor",
    )
    token = models.CharField(max_length=16, null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    last_user_agent = models.CharField(max_length=1000, null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    attempts = models.SmallIntegerField(default=0)
    delivery_type = models.CharField(max_length=8,
                                     choices=DELIVERY_TYPE_CHOICES,
                                     default=SMS)

    def __str__(self):
        return f"{self.user} last validated at {self.validated_at}"

    def required(self, user_agent: str) -> bool:
        """Ascertain if two factor is required."""
        if self.validated_at is None:
            expired = True
        else:
            last_validated = (timezone.now() - self.validated_at).days
            expired = last_validated > settings.TWO_FACTOR_AUTH_VALID_DAYS
        return settings.TWO_FACTOR_AUTH_REQUIRED and any(
            [
                user_agent != self.last_user_agent,
                expired,
            ]
        )

    @check_locked
    def deliver_token(self, user_agent: str):
        """Send user a 2FA token.

        Generates a new 2FA token and delivers it to the user over
        `TwoFactorAuth.delivery_type`.
        """
        self.last_user_agent = user_agent
        self.validated_at = None
        self.token = str(random.randint(10000, 99999))
        self.generated_at = timezone.now()
        self.save()
        # TODO-TRV2 add code to deliver 2FA token
        # see core.models.TwoFactorAuth.two_factor_auth

    @check_locked
    def validate_token(self, token: str, user_agent: str) -> bool:
        """Validate 2FA token.

        Check 2FA token is the same as one we generated and is not expired
        (based on the validity period for the delivery type).
        """
        valid_seconds = {
            TwoFactorAuth.SMS: settings.TWO_FACTOR_CODE_SMS_VALID_MINUTES,
            TwoFactorAuth.EMAIL: settings.TWO_FACTOR_CODE_EMAIL_VALID_MINUTES,
        }.get(self.delivery_type) * 60

        token_age = (timezone.now() - self.generated_at).seconds
        expired = token_age > valid_seconds
        valid = token == self.token
        same_agent = self.last_user_agent == user_agent

        if success := all([not expired, valid, same_agent]):
            self._success(user_agent)
        else:
            logger.info(
                f"2FA validation failed for {self.user}: "
                f"expired={expired}; valid:{valid}; same agent: {same_agent}"
            )
            self._fail()
        return success

    def _success(self, user_agent):
        """Mark 2FA successful."""
        self.validated_at = timezone.now()
        self.last_user_agent = user_agent
        self.attempts = 0
        self.locked_until = None
        self.save()

    def _fail(self):
        """Mark 2FA failed."""
        self.attempts += 1
        if self.attempts > settings.TWO_FACTOR_MAX_ATTEMPTS:
            self._lock()
        self.save()

    def _lock(self):
        """Prohibit further 2FA attempts for cool off period."""
        logger.info(f"2FA validation locked for {self.user}")
        self.locked_until = timezone.now() + datetime.timedelta(
            minutes=settings.TWO_FACTOR_LOCK_MINUTES
        )
        self.save()
