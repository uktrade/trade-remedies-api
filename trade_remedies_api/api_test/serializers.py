from rest_framework import serializers, EmailField
from core.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "..."]  # Add other fields


class TestUserSerializer(serializers.Serializer):
    email = EmailField()

    def create(self, validated_data):
        user = User.objects.create(**validated_data, username="foo",)
        user.set_password("password1")
        user.save()
        return user
