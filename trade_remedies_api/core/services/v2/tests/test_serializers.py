from cases.models import Case
from config.test_bases import CaseSetupTestMixin
from core.services.v2.users.serializers import UserSerializer


class TestUserSerializer(CaseSetupTestMixin):
    def test_normal(self):
        serializer = UserSerializer(instance=self.user)
        assert not serializer.data["cases"]
        assert not serializer.data["organisation"]
        assert "password" not in serializer.data

    def test_cases(self):
        self.case_object.assign_user(
            self.user, created_by=self.user, organisation=self.organisation, relax_security=True
        )
        serializer = UserSerializer(instance=self.user)
        assert serializer.data["cases"]
        assert len(serializer.data["cases"]) == 1
        assert str(self.case_object.id) == serializer.data["cases"][0]["id"]

    def test_organisation(self):
        self.organisation_user = self.organisation.assign_user(
            user=self.user, security_group=self.owner_group
        )
        serializer = UserSerializer(instance=self.user)
        assert serializer.data["organisation"]
        assert str(self.organisation.id) == serializer.data["organisation"]["id"]
