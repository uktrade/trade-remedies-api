from django.contrib.auth.models import Group
from rest_framework import serializers

from core.models import User
from core.serializers import UserSerializer


class ConditionSerializer(serializers.Serializer):
    condition = serializers.CharField()
    value = serializers.BooleanField()
    required = serializers.BooleanField()


class FlagSerializer(serializers.Serializer):
    name = serializers.EmailField()
    conditions = ConditionSerializer(many=True)
    users_in_group = serializers.SerializerMethodField('get_users_in_group')

    @staticmethod
    def get_users_in_group(value):
        return UserSerializer(User.objects.filter(groups__name=value.name), many=True).data
