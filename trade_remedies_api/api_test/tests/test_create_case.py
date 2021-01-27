from django.test import TestCase

from rest_framework.test import APIRequestFactory
from api_test.views import CaseList
from api_test.serializers import TEST_EMAIL
from django.contrib.auth.models import Group

from core.models import User
from cases.models import (
    Case,
)

from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
)


from cases.tests.test_case import get_case_fixtures


class CreateCaseTest(TestCase):
    fixtures = get_case_fixtures("sectors.json",)

    def setUp(self):
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)

    def test_create_case(self):
        factory = APIRequestFactory()
        assert Case.objects.all().count() == 0
        request = factory.post("/cases/")
        response = CaseList.as_view()(request)
        assert response.status_code == 201
        # Check that a case was created
        assert Case.objects.all().count() == 1

        # Check the test user was created
        user = User.objects.last()
        assert user.email == TEST_EMAIL
