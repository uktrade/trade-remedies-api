from django.test import TestCase
from django.contrib.auth.models import Group
from core.user_context import UserContext, user_context
from core.models import User


class UserContextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(email="test@user.com", name="Joe Public")
        self.caseworker = User.objects.create(email="case@worker.com", name="Case Worker")

    def test_user_context_sd(self):
        as_none = user_context(None)
        as_user_context = user_context(UserContext(self.user, assisted_by=self.caseworker))
        as_list = user_context([self.user, self.caseworker])
        as_dict = user_context({"user": self.user, "assisted_by": self.caseworker})

        assert isinstance(as_user_context, UserContext)
        assert isinstance(as_list, UserContext)
        assert isinstance(as_dict, UserContext)
        assert as_none is None
        assert as_user_context.user.id == as_list.user.id == as_dict.user.id
        assert as_user_context.assisted_by.id == as_list.assisted_by.id == as_dict.assisted_by.id
