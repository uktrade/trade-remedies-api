from django.http import Http404

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from cases.models import Case

from core.models import User

from organisations.models import Organisation

from api_test.serializers import (
    TEST_EMAIL,
    UserSerializer,
    OrganisationSerializer,
    CaseSerializer,
)

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
        if not request.data or len(request.data) == 0:
            data = {"email": TEST_EMAIL}
        else:
            data = request.data
        serializer = UserSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


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
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


@authentication_classes([])
@permission_classes([])
class OrganisationList(APIView):
    def get(self, request, format=None):
        # Return all organisations
        organisations = Organisation.objects.all()
        serializer = OrganisationSerializer(organisations, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        # Create a test organisation
        serializer = OrganisationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


@authentication_classes([])
@permission_classes([])
class OrganisationDetail(APIView):
    def get_object(self, name):
        try:
            return Organisation.objects.get(name=name)
        except Organisation.DoesNotExist:
            raise Http404

    def get(self, request, name, format=None):
        organisation = self.get_object(name)
        serializer = OrganisationSerializer(organisation)
        return Response(serializer.data)

    def put(self, request, name, format=None):
        serializer = OrganisationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


@authentication_classes([])
@permission_classes([])
class CaseList(APIView):
    def get(self, request, format=None):
        # Return all organisations
        cases = Case.objects.all()
        serializer = CaseSerializer(cases, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        if not request.data or len(request.data) == 0:
            data = {"email": TEST_EMAIL}
        else:
            data = request.data

        serializer = CaseSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


@authentication_classes([])
@permission_classes([])
class CaseDetail(APIView):
    def get_object(self, name):
        try:
            return Case.objects.get(name=name)
        except Case.DoesNotExist:
            raise Http404

    def get(self, request, name, format=None):
        case = self.get_object(name)
        serializer = CaseSerializer(case)
        return Response(serializer.data)

    def put(self, request, name, format=None):
        serializer = CaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view()
@authentication_classes([])
@permission_classes([])
def restore_database(context):
    management.call_command("flush", "--noinput")
    management.call_command("loaddata", "/var/backups/api_test.json")
    return Response(status.HTTP_200_OK)
