import logging

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import router, transaction
from django.db.models.fields.related_descriptors import (
    create_forward_many_to_many_manager as django_create_forward_many_to_many_manager,
)
from django.db.models.signals import post_save
import django.db.models.fields
from django.db.utils import ProgrammingError
from django.dispatch import receiver
from v2_api_client.shared.logging import audit_logger

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

        user_model = get_user_model()

        def custom_create_forward_many_to_many_manager(superclass, rel, reverse=False):
            def custom_add(self, *objs, through_defaults=None):
                original_add(self, *objs, through_defaults=through_defaults)
                if issubclass(self.model, Group):
                    # this is a Group operation from the perspective of the user, e.g,
                    # user.groups.add(group)
                    # let's log it
                    audit_logger.info(
                        "User added to group(s)",
                        extra={"user": self.instance.id, "groups": [str(each) for each in objs]},
                    )
                elif issubclass(self.model, user_model):
                    # this is a User operation from the perspective of the group, e.g,
                    # Group.user_set.add(request.user)
                    # let's log it
                    audit_logger.info(
                        "User added to group",
                        extra={"group": self.instance.name, "users": [each.id for each in objs]},
                    )

            custom_add.alters_data = True

            def custom_remove(self, *objs):
                original_remove(self, *objs)
                if issubclass(self.model, Group):
                    # this is a Group operation from the perspective of the user, e.g,
                    # user.groups.add(group)
                    # let's log it
                    audit_logger.info(
                        "User removed from group(s)",
                        extra={"user": self.instance.id, "groups": [str(each) for each in objs]},
                    )
                elif issubclass(self.model, user_model):
                    # this is a User operation from the perspective of the group, e.g,
                    # Group.objects.get(name=SECURITY_GROUP_SUPER_USER).user_set.add(request.user)
                    # let's log it
                    audit_logger.info(
                        "User removed from group",
                        extra={"group": self.instance.name, "users": [each.id for each in objs]},
                    )

            # conserving these flags from the original method
            custom_add.alters_data = True
            custom_remove.alters_data = True

            # calling the original manager creation method so get the ManyRelatedManager class
            manager = django_create_forward_many_to_many_manager(superclass, rel, reverse)

            # saving the original methods so we can call them later
            original_add = manager.add
            original_remove = manager.remove

            # overriding the original methods with our custom ones (that include logging)
            manager.add = custom_add
            manager.remove = custom_remove

            return manager

        # Monkey patch the add method of the ManyRelatedManager
        # to add logging to ALL group add/remove operations regardless of how they got there
        # this functions the same as post_save listener on the auth_group_user table but that
        # is not possible to implement without setting a custom through table on the User/Group
        # models which is a bit of a pain
        django.db.models.fields.related_descriptors.create_forward_many_to_many_manager = (
            custom_create_forward_many_to_many_manager
        )
