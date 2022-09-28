from django.contrib.auth.models import Group
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from core.models import User
from organisations.models import Organisation
from organisations.services.v2.serializers import (
    OrganisationCaseRoleSerializer,
    OrganisationSerializer,
)
from security.models import OrganisationCaseRole


class OrganisationViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer

    @action(
        detail=True,
        methods=["put"],
        url_name="add_user",
        url_path="add_user",
    )
    def add_user(self, request, *args, **kwargs):
        organisation_object = self.get_object()
        user_object = get_object_or_404(User, pk=request.data["user_id"])
        group_object = get_object_or_404(Group, name=request.data["organisation_security_group"])

        organisation_object.assign_user(
            user=user_object,
            security_group=group_object,
            confirmed=request.data.get("confirmed", False),
        )

        user_object.groups.add(group_object)
        return Response(
            OrganisationSerializer(
                instance=organisation_object, fields=["organisationuser_set"]
            ).data
        )


class OrganisationCaseRoleViewSet(viewsets.ModelViewSet):
    queryset = OrganisationCaseRole.objects.all()
    serializer_class = OrganisationCaseRoleSerializer

    def list(self, request, *args, **kwargs):
        """We can retrieve a single object if we pass a case_id and organisation_id query
        parameter in the request.
        """
        if case_id := self.request.query_params.get("case_id"):
            if organisation_id := self.request.query_params.get("organisation_id"):
                try:
                    organisation_case_role_object = OrganisationCaseRole.objects.get(
                        case_id=case_id, organisation_id=organisation_id
                    )
                    return Response(
                        self.serializer_class(instance=organisation_case_role_object).data
                    )
                except OrganisationCaseRole.DoesNotExist:
                    pass
        return super().list(request, *args, **kwargs)
