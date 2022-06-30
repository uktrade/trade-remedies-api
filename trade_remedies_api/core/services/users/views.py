from django.contrib.auth.models import Group
from rest_framework import viewsets
from rest_framework.decorators import action

from core.models import User
from core.services.users.serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=True, methods=['put'])
    def add_group(self, request, *args, **kwargs):
        group_object = Group.objects.get(name=request.POST["group"])
        user_object = User.objects.get(pk=kwargs["pk"])
        user_object.groups.add(group_object)
        user_object.save()
        return self.retrieve(request, *args, **kwargs)
