import pytest

from authentication.models.user import User


@pytest.mark.django_db(transaction=True)
def test_normalize_email():
    assert User.objects.normalize_email("FoO@bAr.Org") == "foo@bar.org"  # /PS-IGNORE


def test_get_by_natural_key():
    pass


def test_create_user():
    pass


def test_create_superuser():
    pass


def test_str():
    pass


def test_username():
    pass
