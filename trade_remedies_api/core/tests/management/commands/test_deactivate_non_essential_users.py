from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import User


class DeactivateUsers(TestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        # self.helper_sso_patch.stop()
        super().tearDown()

    def test_deactivate_users(self):
        user1 = User.objects.create(email="test1@user.com", name="Joe Public1")
        user2 = User.objects.create(email="test2@user.com", name="Joe Public2")
        user3 = User.objects.create(email="test3@user.com", name="Joe Public3")
        user4 = User.objects.create(email="test3@domain1.com", name="Joe Public4")
        user5 = User.objects.create(email="test3@domain1.com", name="Joe Public5")
        user6 = User.objects.create(email="test3@domain2.com", name="Joe Public6")

        assert user1.is_active
        assert user2.is_active
        assert user3.is_active
        assert user4.is_active
        assert user5.is_active
        assert user6.is_active

        assert User.objects.all().count() == 6
        assert User.objects.filter(is_active=True).count() == 6

        emails = [user1.email, user2.email]

        call_command(
            "deactivate_users",
            exclude=",".join(emails),
            exclude_matching_string="domain1.com",
        )

        assert User.objects.all().count() == 6
        assert User.objects.filter(is_active=True).count() == 4

        user1.refresh_from_db()
        user2.refresh_from_db()
        user3.refresh_from_db()
        user4.refresh_from_db()
        user5.refresh_from_db()
        user6.refresh_from_db()

        assert user1.is_active
        assert user2.is_active
        assert not user3.is_active
        assert user4.is_active
        assert user5.is_active
        assert not user6.is_active
