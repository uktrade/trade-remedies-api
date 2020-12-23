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
