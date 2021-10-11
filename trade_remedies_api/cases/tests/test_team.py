from django.test import TestCase
from django.contrib.auth.models import Group
from cases.models import Case
from security.models import UserCase
from security.exceptions import InvalidAccess
from core.models import User
from security.constants import (
    SECURITY_GROUP_TRA_INVESTIGATOR,
    SECURITY_GROUP_TRA_ADMINISTRATOR,
)

PASSWORD = "A7Hhfa!jfaw@f"


class CaseTeamTest(TestCase):
    """
    Tests for users
    """

    fixtures = [
        "tra_organisations.json",
    ]

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_TRA_ADMINISTRATOR)
        Group.objects.create(name=SECURITY_GROUP_TRA_INVESTIGATOR)
        self.user_1 = User.objects.create_user(
            name="org user",
            email="standard@test.com",  # /PS-IGNORE
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.investigator = User.objects.create_user(
            name="tra user",
            email="trainvestigator@test.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_TRA_INVESTIGATOR],
        )
        self.manager = User.objects.create_user(
            name="tra manager",
            email="tramanager@test.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_TRA_ADMINISTRATOR],
        )
        self.case = Case.objects.create(name="Test Case", created_by=self.investigator)

    def test_tra_manager_assign_user(self):
        result = self.case.assign_user(user=self.investigator, created_by=self.manager)
        assert isinstance(result, UserCase) is True

    def test_tra_user_assign_user(self):
        success = True
        try:
            self.case.assign_user(user=self.investigator, created_by=self.user_1)
        except InvalidAccess:
            success = False
        assert success is False

    def test_public_assign_user(self):
        success = True
        try:
            self.case.assign_user(user=self.investigator, created_by=self.user_1)
        except InvalidAccess:
            success = False
        assert success is False
