from django.urls import reverse

from core.models import Group
from test_functional import FunctionalTestBase

test_group_name = "test group"


class TestUserViewSet(FunctionalTestBase):
    def setUp(self):
        super().setUp()
        self.test_group_object = Group.objects.create(name=test_group_name)

    def test_add_group(self):
        assert self.test_group_object not in self.user.groups.all()
        self.client.put(
            reverse("user-change_group", kwargs={"pk": self.user.pk}),
            data={"group_name": test_group_name},
        )
        assert self.test_group_object in self.user.groups.all()

    def test_delete_group(self):
        self.user.groups.add(self.test_group_object)
        assert self.test_group_object in self.user.groups.all()
        self.client.delete(
            reverse("user-change_group", kwargs={"pk": self.user.pk}),
            data={"group_name": test_group_name},
        )
        assert self.test_group_object not in self.user.groups.all()
