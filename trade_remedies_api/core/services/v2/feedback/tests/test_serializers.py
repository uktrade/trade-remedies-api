from config.test_bases import CaseSetupTestMixin
from core.services.v2.users.serializers import ContactSerializer, UserSerializer



class TestContactSerializer(CaseSetupTestMixin):
    def test_lowercase_email(self):
        serializer = ContactSerializer(
            data={"name": "test", "email": "mixEDEmail@example.cOM"}  # /PS-IGNORE
        )
        new_contact = serializer.save()
        assert new_contact.email.islower()
