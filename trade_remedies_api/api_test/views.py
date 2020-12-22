from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response


@api_view()
@authentication_classes([])
@permission_classes([])
def create_test_case(request):
    return Response({"message": "success"})
