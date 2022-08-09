from django.test import TestCase
import secrets

from config.test_bases import UserSetupTestBase
from core.models import SystemParameter, User, UserProfile
from core.services.registration.serializers import V2RegistrationSerializer, VerifyEmailSerializer
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from core.models import Group


class TestV2RegistrationSerializer(TestCase):
    def setUp(self) -> None:
        self.org_owner_group = Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)

        self.mock_data = {
            "email": "test@example.com",  # /PS-IGNORE
            "password": "123!@£!@£DDSJDJDSsdf",
            "name": "Test",
            "two_factor_choice": "mobile",
            "mobile_country_code": "GB",
            "mobile": "07712345678",
            "uk_employer": "no",
            "company_name": "test org",
            "address_snippet": "test org street",
            "post_code": "1234",
            "company_number": "000000",
            "country": "GB",
            "company_website": "",
            "company_vat_number": "",
            "company_eori_number": "",
            "company_duns_number": "",
        }

    def test_valid_serializer(self):
        user_query = User.objects.filter(email="test@example.com")  # /PS-IGNORE
        organisation_query = Organisation.objects.filter(
            name="test org", companies_house_id="000000"
        )

        self.assertFalse(user_query.exists())
        self.assertFalse(organisation_query.exists())
        serializer = V2RegistrationSerializer(data=self.mock_data)
        self.assertTrue(serializer.is_valid())
        serializer.save()

        self.assertTrue(user_query.exists())
        self.assertTrue(organisation_query.exists())

        new_user_object = User.objects.get(email="test@example.com")  # /PS-IGNORE

        self.assertTrue(UserProfile.objects.filter(user=new_user_object).exists())
        self.assertTrue(new_user_object.contact)
        self.assertEqual(new_user_object.contact.email, "test@example.com")  # /PS-IGNORE
        self.assertEqual(new_user_object.contact.phone, "+447712345678")
        self.assertEqual(new_user_object.contact.post_code, "1234")
        self.assertEqual(new_user_object.contact.address, "test org street")
        self.assertIn(self.org_owner_group, new_user_object.groups.all())
        self.assertEqual(new_user_object.contact.organisation, organisation_query.get())


class TestVerifyEmailSerializer(UserSetupTestBase):
    def test_valid(self):
        self.assertFalse(self.user.userprofile.email_verified_at)
        serializer = VerifyEmailSerializer(
            data={"email_verify_code": self.user.userprofile.email_verify_code},
            instance=self.user.userprofile,
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(self.user.userprofile.email_verified_at)

    def test_invalid_incorrect_code(self):
        serializer = VerifyEmailSerializer(
            data={"email_verify_code": "12345"}, instance=self.user.userprofile
        )
        self.assertFalse(serializer.is_valid())
