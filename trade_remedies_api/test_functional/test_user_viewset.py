from core.models import Group
from rest_framework import status
from test_functional import FunctionalTestBase

test_group_name = "test group"


class TestUserViewSet(FunctionalTestBase):
    def setUp(self):
        super().setUp()
        self.test_group_object = Group.objects.create(name=test_group_name)

    def test_add_group(self):
        assert self.test_group_object not in self.user.groups.all()
        response = self.client.put(
            f"/api/v2/users/{self.user.pk}/add_group/",
            data={"group_name": test_group_name},
        )
        assert self.test_group_object in self.user.groups.all()

    def test_determines_if_user_in_group(self):
        self.user.groups.add(self.test_group_object)
        response = self.client.get(
            f"/api/v2/users/{self.user.pk}/is_user_in_group/?group_name={test_group_name}",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"user_is_in_group": True}

    def test_determines_if_user_not_in_group(self):
        response = self.client.get(
            f"/api/v2/users/{self.user.pk}/is_user_in_group/?group_name={test_group_name}",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"user_is_in_group": False}

    def test_delete_group(self):
        self.user.groups.add(self.test_group_object)
        assert self.test_group_object in self.user.groups.all()
        self.client.delete(
            f"/api/v2/users/{self.user.pk}/add_group/",
            data={"group_name": test_group_name},
        )
        assert self.test_group_object not in self.user.groups.all()
