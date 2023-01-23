from django.contrib.auth.models import Group
from django.http import QueryDict
from rest_framework import status
from rest_framework.test import APITestCase

from cases.tests.test_api import APISetUpMixin
from cases.tests.test_case import get_case_fixtures
from core.models import User
from security.constants import SECURITY_GROUP_SUPER_USER


class UserAPITest(APITestCase, APISetUpMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.setup_test()

        Group.objects.create(name=SECURITY_GROUP_SUPER_USER)

        self.admin = User.objects.create_user(
            name="testboi",
            email="adminsuperuser@gov.uk",  # /PS-IGNORE
            password="Super-secret-password!1",
            groups=[SECURITY_GROUP_SUPER_USER],
            admin=True,
        )

        self.client.force_authenticate(user=self.admin, token=self.admin.auth_token)

    def test_user_create(self):
        response = self.client.get(f"/api/v1/user/{self.admin.id}/", follow=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_name_update(self):
        data = {"name": "<script>super</script>"}

        query_dict = QueryDict("", mutable=True)
        query_dict.update(data)
        query_dict._mutable = False

        response = self.client.post(
            f"/api/v1/user/{self.admin.id}/", query_dict, follow=True, format="multipart"
        )

        self.assertEqual(
            "&lt;script&gt;super&lt;/script&gt;", response.json()["response"]["result"]["name"]
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
