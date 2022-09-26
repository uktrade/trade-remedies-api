from rest_framework import serializers

from core.models import User
from core.services.v2.users.serializers import UserSerializer


class FlagSerializer(serializers.Serializer):
    """
    Normal (not model) serializer for feature flags.

    Returns the name of the serializer, a list of users currently in the named group, and a list of
    all the users not currently in the named group.
    """

    name = serializers.EmailField()
    users_in_group = serializers.SerializerMethodField()
    users_not_in_group = serializers.SerializerMethodField()
    id = serializers.ReadOnlyField(source="name")

    @staticmethod
    def get_users_in_group(value):
        return UserSerializer(
            User.objects.filter(groups__name=value.name),
            many=True,
            fields=["name", "email", "id"]
        ).data

    @staticmethod
    def get_users_not_in_group(value):
        return UserSerializer(
            User.objects.exclude(groups__name=value.name).order_by("name"),
            many=True,
            fields=["name", "email", "id"]
        ).data
