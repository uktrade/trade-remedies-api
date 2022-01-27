import uuid

from django.utils import timezone
import pytest

from authentication.models.user import User


pytestmark = [pytest.mark.version2, pytest.mark.django_db]


def test_normalize_email():
    assert User.objects.normalize_email("FoO@bAr.Org") == "foo@bar.org"  # /PS-IGNORE


def test_get_by_natural_key(fake_user):
    user = User.objects.get_by_natural_key("Test@Example.Com")  # /PS-IGNORE
    assert user.email == user.username


def test_create_user():
    User.objects.create_user(email="another@example.com", password="password")  # /PS-IGNORE
    user = User.objects.get(email="another@example.com")  # /PS-IGNORE
    assert isinstance(user.id, uuid.UUID)
    assert user.username == "another@example.com"  # /PS-IGNORE
    assert not user.is_active
    assert user.last_login is not None
    assert user.last_login < timezone.now()
    assert user.date_joined is not None
    assert user.date_joined < timezone.now()


def test_create_user_no_email():
    with pytest.raises(ValueError) as e:
        User.objects.create_user(email="", password="password")
    assert 'Users must have an email address' in str(e)


def test_create_superuser():
    User.objects.create_superuser(email="admin@example.com", password="password")  # /PS-IGNORE
    admin = User.objects.get(email="admin@example.com")  # /PS-IGNORE
    assert admin.is_admin
    assert admin.is_superuser


def test_str(fake_user):
    user = User.objects.get(email="test@example.com")  # /PS-IGNORE
    assert str(user) == "test@example.com"  # /PS-IGNORE


def test_username(fake_user):
    user = User.objects.get(email="test@example.com")  # /PS-IGNORE
    assert user.email == user.username
