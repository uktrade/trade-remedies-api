from django.http import Http404

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from core.models import User

from api_test.serializers import UserSerializer, TestUserSerializer

from django.core import management


@authentication_classes([])
@permission_classes([])
class UserList(APIView):
    def get(self, request, format=None):
        # Return all users
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        # Create a test user
        print(f"request = {request.data}")
        serializer = TestUserSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED,)

        print(f"serializer.errors = {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST,)


@authentication_classes([])
@permission_classes([])
class UserDetail(APIView):
    def get_object(self, email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise Http404

    def get(self, request, email, format=None):
        # Return single user
        user = User.objects.get(email=email)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, email, format=None):
        user = self.get_object(email)
        serializer = TestUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED,)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST,)


@api_view()
@authentication_classes([])
@permission_classes([])
def restore_database(context):
    management.call_command("flush", "--noinput")
    management.call_command("loaddata", "/var/backups/api_test.json")
    return Response(status.HTTP_200_OK)
