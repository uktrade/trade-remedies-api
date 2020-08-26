from django.contrib.auth.models import Group
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
)


def before_feature(context, feature):
    context.fixtures = ["actions.json", "roles.json"]
    return context


def before_scenario(context, scenario):
    context.org_group_owner = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
    context.org_group_user = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
    return context


def django_ready(context):
    context.django = True
    return context
