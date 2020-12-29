from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response

from core.models import User


@api_view()
@authentication_classes([])
@permission_classes([])
def create_test_case(request):
    return Response({"message": "success"})


@api_view()
@authentication_classes([])
@permission_classes([])
def create_test_user(request, email, password, group):
    user = User.objects.create_user(
        name="test user",
        email=email,
        password=password,
        groups=[group],
        country="GB",
        timezone="Europe/London",
        phone="012345678",
    )
    return Response({"message": "success"})


# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# class Users(APIView):
#     def get(self, request, format=None):
#         # Return all users
#         users = User.objects.all()
#         serializer = UserSerializer(users, many=True)
#         return Response(serializer.data)
#     def get(self, request, pk, format=None):
#         # Return single user
#         user = self.get_object(pk)
#         serializer = UserSerializer(snippet)
#         return Response(serializer.data)
#     def post(self, request, format=None):
#         # Create a test user
#         serializer = TestUserSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(
#                 serializer.data,
#                 status=status.HTTP_201_CREATED,
#             )
#         return Response(
#             serializer.errors,
#             status=status.HTTP_400_BAD_REQUEST,
#         )
