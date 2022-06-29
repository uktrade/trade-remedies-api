from rest_framework import serializers

from core.models import User
from core.services.users.serializers import UserSerializer


class ConditionSerializer(serializers.Serializer):
    condition = serializers.CharField()
    value = serializers.BooleanField()
    required = serializers.BooleanField()


class FlagSerializer(serializers.Serializer):
    name = serializers.EmailField()
    conditions = ConditionSerializer(many=True)
    users_in_group = serializers.SerializerMethodField()
    users_not_in_group = serializers.SerializerMethodField()

    @staticmethod
    def get_users_in_group(value):
        return UserSerializer(User.objects.filter(groups__name=value.name), many=True).data

    @staticmethod
    def get_users_not_in_group(value):
        return UserSerializer(User.objects.exclude(groups__name=value.name), many=True).data
