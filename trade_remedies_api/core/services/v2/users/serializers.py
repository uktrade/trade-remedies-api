from django.contrib.auth.models import Group
from rest_framework import serializers

from contacts.models import Contact
from core.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ("password",)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"

    def to_internal_value(self, data):
        data = data.copy()  # Making the QueryDict mutable
        if security_group := data.get("security_group"):
            # We can pass a security group in the request.POST which we can use
            # to look up a Group object
            role_object = Group.objects.get(name=security_group)
            data[""] = role_object.pk
        return super().to_internal_value(data)
