import logging

from security.models import OrganisationUser
from organisations.models import get_organisation
from cases.models import get_case
from django.contrib.auth.models import Group, Permission
from .constants import GROUPS, GROUP_PERMISSIONS, ADDITIONAL_PERMISSIONS

logger = logging.getLogger(__name__)


def validate_user_organisation(user, organisation):
    """
    Validate a user can access this organisation.
    This is true if the user is either a member of the organisation,
    or is a case worker.
    TODO: At the moment TRA side is fairly open. Consider this.
    """
    if user.is_tra():
        return True
    organisation = get_organisation(organisation)
    org_user = OrganisationUser.objects.filter(organisation=organisation, user=user).exists()
    return org_user


def validate_user_case(user, case, organisation):
    """
    Validate the user has access to this case and organisation
    Fairly simplistic at the moment
    """
    if user.is_tra():
        return True
    case = get_case(case)
    organisation = get_organisation(organisation)
    return user.has_case_access(case, organisation)


# Setup/Bootsrapping utility funcitons
def create_groups():
    for group_data in GROUPS:
        group, created = Group.objects.get_or_create(name=group_data[0])
        logger.info(f"{group_data[0]} created? {created}")


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
            logger.info("{0} permission not found".format(permission_name), exc_info=True)
