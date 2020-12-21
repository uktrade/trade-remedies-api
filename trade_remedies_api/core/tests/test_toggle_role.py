from django.test import TestCase
from django.contrib.auth.models import Group
from core.models import User
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
)

PASSWORD = "A7Hhfa!jfaw@f"


class UserTest(TestCase):
    """
    Tests for users
    """

    fixtures = [
        "tra_organisations.json",
    ]

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)

    def test_toggle_role(self):
        user = User.objects.create_user(
            name="test user",
            email="test@example.com",
            password=PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
            country="GB",
            timezone="Europe/London",
            phone="077931231234",
        )
        user_obj = User.objects.get(id=user.id)
        group_queryset = user_obj.groups.all()
        # assigned to 1 group before the command
        assert group_queryset.count() == 1
        user.toggle_role(SECURITY_GROUP_ORGANISATION_OWNER)
        user_obj = User.objects.get(id=user.id)
        group_queryset = user_obj.groups.all()
        # assigned to 1 group before the command
        assert group_queryset.count() == 1
