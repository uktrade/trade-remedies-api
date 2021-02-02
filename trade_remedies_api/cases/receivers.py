import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone
from security.models import UserCase
from organisations.models import Organisation
from cases.models import Case
from core.models import User


logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=UserCase)
def log_deleted_usercase(sender, instance, **kwargs):
    """There is bug where users cannot see their cases in the public portal.
        The bug is caused by them not having a record in UserCase table.
        This function logs the deletion of a record: with the Audit log,
        it may help to identify the chain of events causing the bug.
    """
    logger.info(
        f"UserCase record deleted: "
        f"user_id = {instance.user.id}, email = {instance.user.email}, "
        f"case_id = {instance.case.id}, case = {instance.case.name}, "
        f"organisation_id = {instance.organisation.id}, organisation = {instance.organisation.name} "
    )


@receiver(pre_delete, sender=User)
def log_deleted_user(sender, instance, **kwargs):
    logger.info(f"User record deleted: user_id = {instance.id}, email = {instance.email}, ")


@receiver(pre_delete, sender=Case)
def log_deleted_case(sender, instance, **kwargs):
    logger.info(f"Case record deleted: case_id = {instance.id}, case = {instance.name}, ")


@receiver(pre_delete, sender=Organisation)
def log_deleted_organisation(sender, instance, **kwargs):
    logger.info(
        f"Organisation record deleted: organisation_id = {instance.id}, organisation = {instance.name}, "
    )
