from django.test import TestCase

from rest_framework.test import APIRequestFactory
from core.models import User
from api_test.views import Users
from api_test.serializers import TEST_EMAIL


class CreateUserTest(TestCase):
    def test_can_create_specific_user(self):
        factory = APIRequestFactory()
        test_email = "test@test.com"
        request = factory.post("/users/", {"email": test_email})
        response = Users.as_view()(request)
        assert response.status_code == 201
        # Check the user was created as expected
        user = User.objects.last()
        assert user.email == test_email

    def test_can_create_user(self):
        factory = APIRequestFactory()
        request = factory.post("/users/")
        response = Users.as_view()(request)
        assert response.status_code == 201
        # Check the user was created as expected
        user = User.objects.last()
        assert user.email == TEST_EMAIL
        # now use get to read the user
        request = factory.get("/users/")
        response = Users.as_view()(request)
        print(f"response.data[0] = {response.data[0]['email']}")
        assert response.status_code == 200
        assert response.data[0]["email"] == TEST_EMAIL
