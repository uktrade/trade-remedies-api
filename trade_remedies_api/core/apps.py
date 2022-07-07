import logging

from django.apps import AppConfig
from django.conf import settings
from django.db.utils import ProgrammingError

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from django.contrib.auth.models import Group

        try:
            for flag in settings.FLAGS:
                group_object, created = Group.objects.update_or_create(name=flag)
                if created:
                    logger.debug(f"Feature Flag Group {flag} has been created")
            # Now we want to delete all old feature flags which we may have deleted from the FLAGS var
            Group.objects.filter(name__startswith=settings.FEATURE_FLAG_PREFIX).exclude(
                name__in=settings.FLAGS
            ).delete()
        except ProgrammingError:
            logger.error(
                "There was an error creating some of "
                "the feature flag groups during app initialisation"
            )
