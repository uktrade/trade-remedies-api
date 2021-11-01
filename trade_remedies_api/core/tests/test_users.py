from django.test import TestCase
from django.contrib.auth.models import Group
from core.models import User

PASSWORD = "A7Hhfa!jfaw@f"


class UserTest(TestCase):
    """
    Tests for users
    """

    fixtures = [
        "tra_organisations.json",
    ]

    def setUp(self):
        Group.objects.create(name="Administrator")
        Group.objects.create(name="Test Role")

    def test_user_create(self):
        """
        Test for user creation via User.objects.create_user
        """
        user = User.objects.create_user(
            name="test user",
            email="test@example.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=["Administrator"],
            country="GB",
            timezone="Europe/London",
            phone="077931231234",
        )
        user = User.objects.get(id=user.id)
        group = Group.objects.get(name="Administrator")
        assert user.email == "test@example.com"  # /PS-IGNORE
        assert user.phone == "+4477931231234"
        assert group.user_set.filter(id=user.id).exists()

    def test_user_update(self):
        """
        Test for user creation via User.objects.create_user
        """
        new_user = User.objects.create_user(
            name="test user",
            email="test@example.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=["Administrator"],
            country="GB",
            timezone="Europe/London",
            phone="077931231234",
        )
        user = User.objects.update_user(
            name="other user",
            user_id=new_user.id,
            password=PASSWORD + "12",
            country="US",
            phone="4151112345",
            timezone="America/Los_Angeles",
            groups=["Test Role"],
        )
        user.refresh_from_db()
        group = Group.objects.get(name="Test Role")
        assert user.email == "test@example.com"  # /PS-IGNORE
        assert user.phone == "+14151112345"
        assert group.user_set.filter(id=user.id).exists()
