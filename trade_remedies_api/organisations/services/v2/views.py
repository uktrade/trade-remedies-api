from rest_framework import viewsets
from rest_framework.response import Response

from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationCaseRoleSerializer, \
    OrganisationSerializer
from security.models import OrganisationCaseRole


class OrganisationViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer


class OrganisationCaseRoleViewSet(viewsets.ModelViewSet):
    queryset = OrganisationCaseRole.objects.all()
    serializer_class = OrganisationCaseRoleSerializer

    def list(self, request, *args, **kwargs):
        if case_id := self.request.query_params.get('case_id'):
            if organisation_id := self.request.query_params.get("organisation_id"):
                try:
                    organisation_case_role_object = OrganisationCaseRole.objects.get(
                        case_id=case_id,
                        organisation_id=organisation_id
                    )
                    return Response(
                        self.serializer_class(instance=organisation_case_role_object).data
                    )
                except OrganisationCaseRole.DoesNotExist:
                    pass
        return super().list(request, *args, **kwargs)
