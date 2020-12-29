from rest_framework.test import APIRequestFactory
from core.models import User


def test_can_create_user():
    factory = APIRequestFactory()
    test_email = "test@test.com"
    response = factory.post("/users/", {"email": test_email})
    assert response.status_code == 201
    # Check the user was created as expected
    user = User.objects.last()
    assert user.email == test_email
