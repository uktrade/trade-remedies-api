from config.test_bases import CaseSetupTestMixin
from core.services.v2.users.serializers import ContactSerializer, UserSerializer


class TestUserSerializer(CaseSetupTestMixin):
    def test_normal(self):
        serializer = UserSerializer(instance=self.user)
        assert not serializer.data["cases"]
        assert not serializer.data["organisation"]

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

    def test_password_cant_be_updated(self):
        hashed_password = self.user.password
        serializer = UserSerializer(
            instance=self.user,
            data={
                "password": "new_testpassword123!DD",
                "name": "new_name",
                "email": self.user.email,
            },
        )
        assert serializer.is_valid()
        serializer.save()
        self.user.refresh_from_db()
        assert hashed_password == self.user.password
        assert self.user.name == "new_name"

    def test_unusable_password(self):
        serializer = UserSerializer(
            data={
                "name": "new user",
                "email": "newww@example.com",  # /PS-IGNORE
            }
        )
        assert serializer.is_valid()
        new_user = serializer.save()
        assert not new_user.has_usable_password()

    def test_invalid_password(self):
        serializer = UserSerializer(
            data={
                "email": "new_user@example.com",  # /PS-IGNORE
                "name": "new user",
                "password": "invalid_password",
            }
        )
        assert not serializer.is_valid()


class TestContactSerializer(CaseSetupTestMixin):
    def test_lowercase_email(self):
        serializer = ContactSerializer(
            data={"name": "test", "email": "mixEDEmail@example.cOM"}  # /PS-IGNORE
        )
        assert serializer.is_valid()
        new_contact = serializer.save()
        assert new_contact.email.islower()

    def test_mobile_number_without_country_code_no_phone(self):
        serializer = ContactSerializer(instance=self.contact_object)
        assert not serializer.data["mobile_number_without_country_code"]

    def test_mobile_number_without_country_code_valid_number(self):
        self.contact_object.phone = "+447123456789"
        serializer = ContactSerializer(instance=self.contact_object)
        assert serializer.data["mobile_number_without_country_code"] == "7123456789"

    def test_mobile_number_without_country_code_invalid_number(self):
        self.contact_object.phone = "+123"
        serializer = ContactSerializer(instance=self.contact_object)
        assert not serializer.data["mobile_number_without_country_code"]
