from rest_framework import serializers
from core.models import User

TEST_PASSWORD= "A7Hhfa!jfaw@f"
TEST_EMAIL= "ttt.aaa@d.com"

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "group"]


class TestUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    id = serializers.CharField(required=False)

    def create(self, validated_data):
        try:
            email = validated_data.pop("email")
        except KeyError:
            email = TEST_EMAIL

        user = User.objects.create_user(
            name="test user",
            email=email,
            password=TEST_PASSWORD,
            groups=[],
            country="GB",
            timezone="Europe/London",
            phone="012345678",
        )
        return user
