from rest_framework import serializers
from core.models import User

from security.constants import (
    SECURITY_GROUP_ORGANISATION_USER,
)

TEST_PASSWORD= "A7Hhfa!jfaw@f"
TEST_EMAIL= "ttt.aaa@d.com"

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email"]


class TestUserSerializer(serializers.Serializer):
    email = serializers.EmailField(default=TEST_EMAIL)
    id = serializers.CharField(required=False)

    def create(self, validated_data):
        email = validated_data.pop("email")
        user = User.objects.create_user(
            name="test user",
            email=email,
            password=TEST_PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_USER],
            country="GB",
            timezone="Europe/London",
            phone="012345678",
        )
        return user
