from rest_framework import serializers
from core.models import User

from organisations.models import Organisation

from security.constants import SECURITY_GROUP_ORGANISATION_OWNER

TEST_PASSWORD = "A7Hhfa!jfaw@f"
TEST_EMAIL = "ttt.aaa@d.com"

class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    organisations=OrganisationSerializer(many=True, read_only=True)
    class Meta:
        model = User
        fields = ["id", "email", "organisations"]


class TestUserSerializer(serializers.Serializer):
    email = serializers.EmailField(default=TEST_EMAIL)
    id = serializers.CharField(required=False)
    organisations=OrganisationSerializer(many=True, read_only=True)

    def create(self, validated_data):
        email = validated_data.pop("email")
        user = User.objects.create_user(
            name="test user",
            email=email,
            password=TEST_PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
            country="GB",
            timezone="Europe/London",
            phone="012345678",
            organisation_name= 'Test Organisation',
            organisation_country= 'GB',
            companies_house_id= 'TE5 TS1',
            organisation_address= 'Test address',
        )
        return user


