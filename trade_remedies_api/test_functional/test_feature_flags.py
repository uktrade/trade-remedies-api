from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from core.models import Group, User
from test_functional import FunctionalTestBase
from security.tests.test_security import PASSWORD

test_group_name = f'{settings.FEATURE_FLAG_PREFIX}_TEST_GROUP'


@override_settings(
    FLAGS={
        test_group_name: [
            {'condition': 'PART_OF_GROUP', 'value': True, "required": True},
        ],
    }
)
class TestFeatureFlagSerializer(FunctionalTestBase):

    def setUp(self) -> None:
        super().setUp()
        self.user_one = User.objects.create_user(
            email="user_one@example.com",
            password=PASSWORD
        )
        self.user_two = User.objects.create_user(
            email="user_two@example.com",
            password=PASSWORD
        )
        self.test_group_object = Group.objects.create(name=test_group_name)

    def test_list(self):
        response = self.client.get(reverse("django-feature-flags-list"))
        assert response.status_code == 200
        response_data = response.json()["response"]["results"]
        assert len(response_data) == 1
        assert response_data[0]["name"] == test_group_name
        assert len(response_data[0]["users_in_group"]) == 0
        assert len(response_data[0]["users_not_in_group"]) == 3

    def test_list_in_group(self):
        # First we add a user to the group and see if that membership is reflected in the response
        self.user_one.groups.add(self.test_group_object)
        response = self.client.get(reverse("django-feature-flags-list"))
        response_data = response.json()["response"]["results"]
        assert response_data[0]["name"] == test_group_name
        assert len(response_data[0]["users_in_group"]) == 1
        assert len(response_data[0]["users_not_in_group"]) == 2

        assert response_data[0]["users_in_group"][0]["id"] == str(self.user_one.pk)
        assert response_data[0]["users_not_in_group"][1]["id"] == str(self.user_two.pk)

    def test_retrieve(self):
        response = self.client.get(
            reverse("django-feature-flags-detail", kwargs={"pk": test_group_name})
        )
        assert response.status_code == 200
        response_data = response.json()["response"]["result"]
        assert response_data["name"] == test_group_name
        assert len(response_data["users_not_in_group"]) == 3

    def test_retrieve_not_found(self):
        response = self.client.get(
            reverse("django-feature-flags-detail", kwargs={"pk": "GROUP_NOT_CREATED"})
        )
        assert response.status_code == 404
