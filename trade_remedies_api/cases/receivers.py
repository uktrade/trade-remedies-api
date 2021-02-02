import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from security.models import UserCase
from organisations.models import Organisation
from cases.models import Case
from core.models import User


logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=UserCase)
def log_deleted_usercase(sender, instance, **kwargs):
    logger.info(
        f"UserCase record deleted: "
        f"user_id = {instance.user.id}, "
        f"email = {instance.user.email}, "
        f"case_id = {instance.case.id}, "
        f"case = {instance.case.name}, "
        f"organisation_id = {instance.organisation.id}, "
        f"organisation = {instance.organisation.name} "
    )


@receiver(pre_delete, sender=User)
def log_deleted_user(sender, instance, **kwargs):
    logger.info(f"User record deleted: "
                f"user_id = {instance.id}, "
                f"email = {instance.email}, ")


@receiver(pre_delete, sender=Case)
def log_deleted_case(sender, instance, **kwargs):
    logger.info(f"Case record deleted: "
                f"case_id = {instance.id},"
                f" case = {instance.name}, ")


@receiver(pre_delete, sender=Organisation)
def log_deleted_organisation(sender, instance, **kwargs):
    logger.info(
        f"Organisation record deleted: "
        f"organisation_id = {instance.id}, "
        f"organisation = {instance.name}, "
    )
