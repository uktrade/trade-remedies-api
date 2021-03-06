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
    try:
        message = (
            f"UserCase record deleted: "
            f"user_id = {getattr(instance.user, 'id', 'unknown')}, "
            f"email = {getattr(instance.user, 'email', 'unknown')}, "
            f"case_id = {getattr(instance.case, 'id', 'unknown')}, "
            f"case = {getattr(instance.case, 'name', 'unknown')}, "
            f"organisation_id = {getattr(instance.organisation, 'id', 'unknown')}, "
            f"organisation = {getattr(instance.organisation, 'name', 'unknown')} "
        )
    except AttributeError as e:
        message = f"UserCase record deleted: Unable to log all details because: {e}"
    logger.info(message)


@receiver(pre_delete, sender=User)
def log_deleted_user(sender, instance, **kwargs):
    try:
        message = (
            f"User record deleted: "
            f"user_id = {getattr(instance, 'id', 'unknown')}, "
            f"email = {getattr(instance, 'email', 'unknown')}"
        )
    except AttributeError as e:
        message = f"User record deleted: Unable to log all details because: {e}"
    logger.info(message)


@receiver(pre_delete, sender=Case)
def log_deleted_case(sender, instance, **kwargs):
    try:
        message = (
            f"Case record deleted: "
            f"case_id = {getattr(instance, 'id', 'unknown')}, "
            f"case = {getattr(instance, 'name', 'unknown')}"
        )
    except AttributeError as e:
        message = f"Case record deleted: Unable to log all details because: {e}"
    logger.info(message)


@receiver(pre_delete, sender=Organisation)
def log_deleted_organisation(sender, instance, **kwargs):
    try:
        message = (
            f"Organisation record deleted: "
            f"organisation_id = {getattr(instance, 'id', 'unknown')}, "
            f"organisation = {getattr(instance, 'name', 'unknown')}"
        )
    except AttributeError as e:
        message = f"Organisation record deleted: Unable to log all details because: {e}"
    logger.info(message)
