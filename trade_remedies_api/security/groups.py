import logging

from django.contrib.auth.models import Group, Permission

logger = logging.getLogger(__name__)


GROUPS = [
    ("Super User", "Has all permissions and can override security restrictions"),
    ("TRA Administrator", "TRA Administrator"),
    ("TRA Investigator", "TRA Investigator"),
    ("Head of Investigation", "Head of Investigation"),
    ("Lead Investigator", "Lead Investigator"),
    ("Organisation Owner", "A member of an organisation with owner access"),
    ("Organisation User", "A member of an organisation with standard access"),
]

GROUP_PERMISSIONS = {}
GROUP_PERMISSIONS["TRA Investigator"] = []
GROUP_PERMISSIONS["TRA Administrator"] = GROUP_PERMISSIONS["TRA Investigator"] + [
    "core.add_user",
    "core.change_user",
    "core.delete_user",
]
GROUP_PERMISSIONS["Organisation User"] = []
GROUP_PERMISSIONS["Organisation Owner"] = GROUP_PERMISSIONS["Organisation User"] + []


PERMISSION_MODELS = [
    "core",
]

# Any additional permissions to be assigned to the Super User
ADDITIONAL_PERMISSIONS = []

# The initial user will be assigned the Super User group which provides them with all
# permissions, and cannot be unset. New users will default to the following group
# configuration
DEFAULT_USER_PERMISSIONS = []

DEFAULT_ADMIN_PERMISSIONS = DEFAULT_USER_PERMISSIONS + [
    "Administrator",
]


# Setup/Bootsrapping utility funcitons


def create_groups():
    for group_data in GROUPS:
        group, created = Group.objects.get_or_create(name=group_data[0])
        logger.info("\t{0} created? {1}".format(group_data[0], created))


def assign_group_permissions():
    all_permissions = []
    for group_name in GROUP_PERMISSIONS:
        logger.info(
            "Assigning {0} permissions to {1}".format(
                len(GROUP_PERMISSIONS[group_name]), group_name
            )
        )
        all_permissions += GROUP_PERMISSIONS[group_name]
        group, created = Group.objects.get_or_create(name=group_name)
        for permission_name in GROUP_PERMISSIONS[group_name]:
            try:
                app, perm = permission_name.split(".")
                permission = Permission.objects.get(codename=perm, content_type__app_label=app)
                group.permissions.add(permission)
            except Permission.DoesNotExist:
                logger.error("\t{0} -> Does not exist".format(permission_name), exc_info=True)
    logger.info("Assigning {0} Super User permissions".format(len(all_permissions)))
    superuser = Group.objects.get(name="Super User")
    for permission_name in all_permissions + ADDITIONAL_PERMISSIONS:
        try:
            app, perm = permission_name.split(".")
            permission = Permission.objects.get(codename=perm, content_type__app_label=app)
            superuser.permissions.add(permission)
        except Permission.DoesNotExist:
            logger.error("{0} permission not found".format(permission_name), exc_info=True)
