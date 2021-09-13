from django.core.management import call_command
from django.core.management.base import CommandError

from django.test import TestCase
from core.models import User
from django.contrib.auth.models import Group
from security.constants import SECURITY_GROUP_ORGANISATION_USER

PASSWORD = "A7Hhfa!jfaw@f"


class PatchUserCommandTest(TestCase):
    fixtures = ["tra_organisations.json", "actions.json", "roles.json"]

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)

    def test_patch_user_command_wrong_email(self):
        with self.assertRaises(CommandError):
            call_command("patch_user", "does_not_exist")

    def test_patch_user_command_user_with_group(self):
        email_with_group = "test.user@test.test"#PS-IGNORE
        user_obj = User.objects.create_user(
            name="user with group",
            email=email_with_group,
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_USER],
        )
        group_queryset = user_obj.groups.all()
        # assigned to 1 group before the command
        assert group_queryset.count() == 1
        with self.assertRaises(CommandError):
            call_command("patch_user", email_with_group)
        group_queryset = user_obj.groups.all()
        # still assigned to 1 group after the command
        assert group_queryset.count() == 1

    def test_patch_user_command(self):
        email_no_group = "test1.user@test.test"#PS-IGNORE
        user_obj = User.objects.create_user(
            name="user without group",
            email=email_no_group,
            password=PASSWORD,
            assign_default_groups=False,
        )
        group_queryset = user_obj.groups.all()
        # no group before the command
        assert group_queryset.count() == 0

        call_command("patch_user", email_no_group)
        group_queryset = user_obj.groups.all()
        # assigned to 1 group after the command
        assert group_queryset.count() == 1
