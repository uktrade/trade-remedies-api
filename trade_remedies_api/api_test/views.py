from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from core.models import User

from api_test.serializers import UserSerializer, TestUserSerializer


@api_view()
@authentication_classes([])
@permission_classes([])
def create_test_case(request):
    return Response({"message": "success"})


@authentication_classes([])
@permission_classes([])
class Users(APIView):
    def get(self, request, format=None):
        # Return all users
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    # def get(self, request, pk, format=None):
    #     # Return single user
    #     user = User.objects.get(pk=pk)
    #     serializer = UserSerializer(user)
    #     return Response(serializer.data)

    def post(self, request, format=None):
        # Create a test user
        print(f"request = {request.data}")
        serializer = TestUserSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED,)

        print(f"serializer.errors = {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST,)
