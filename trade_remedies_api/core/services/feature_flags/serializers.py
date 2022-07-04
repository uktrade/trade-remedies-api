from rest_framework import serializers

from core.models import User
from core.services.users.serializers import UserSerializer


class FlagSerializer(serializers.Serializer):
    name = serializers.EmailField()
    users_in_group = serializers.SerializerMethodField()
    users_not_in_group = serializers.SerializerMethodField()

    @staticmethod
    def get_users_in_group(value):
        return UserSerializer(User.objects.filter(groups__name=value.name), many=True).data

    @staticmethod
    def get_users_not_in_group(value):
        return UserSerializer(User.objects.exclude(groups__name=value.name), many=True).data
