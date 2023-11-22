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

        assert user1.is_active
        assert user2.is_active
        assert user3.is_active
        assert User.objects.all().count() == 4
        assert User.objects.filter(is_active=True).count() == 4

        emails = [user1.email, user2.email]

        call_command("deactivate_users", emails=",".join(emails))

        assert User.objects.all().count() == 3
        assert User.objects.filter(is_active=True).count() == 1

        user1.refresh_from_db()
        user2.refresh_from_db()
        user3.refresh_from_db()

        assert not user1.is_active
        assert not user2.is_active
        assert user3.is_active
