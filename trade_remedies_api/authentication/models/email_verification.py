import logging

from django.conf import settings
from django.dispatch import receiver
from django.db import models
from django.utils import crypto, timezone

logger = logging.getLogger(__name__)

CODE_LENGTH = 64


class EmailVerification(models.Model):
    """Email Verification Model.

    Persists the state of a user's email verification.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="email_verification"
    )
    code = models.CharField(max_length=CODE_LENGTH, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def send(self):
        """Send an email verification."""
        self.code = crypto.get_random_string(CODE_LENGTH)
        link = f"{settings.PUBLIC_ROOT_URL}/email/verify/?code={self.code}"
        context = {
            "verification_link": link
        }
        # TODO-TRV2 Implement a new notification package to centralise all
        #  notification logic, template IDs etc so we can do something like:
        #
        #  notification.send(
        #      channels=[notification.EMAIL,],
        #      recipients=[self.user.email,],
        #      template=notification.template("NOTIFY_VERIFY_EMAIL"),
        #      context=context
        #  )
        self.sent_at = timezone.now()
        self.verified_at = None
        self.save()


@receiver(models.signals.post_save, sender="authentication.User")
def verify_email(sender, instance, created, **kwargs):  # noqa
    """Post User save signal handler.

    New user's need to verify their email address.
    """
    if created:
        instance.email_verification = EmailVerification(user=instance)
        instance.email_verification.send()
