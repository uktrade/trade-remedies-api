from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
import pgtransaction
from config.context import db
from config.viewsets import BaseModelViewSet
from core.models import User
from organisations.models import DuplicateOrganisationMerge, Organisation, OrganisationMergeRecord
from organisations.services.v2.pagination import StandardResultsSetPagination
from organisations.services.v2.serializers import (
    DuplicateOrganisationMergeSerializer,
    OrganisationCaseRoleSerializer,
    OrganisationListSerializer,
    OrganisationMergeRecordSerializer,
    OrganisationSerializer,
)
from security.models import OrganisationCaseRole


class OrganisationViewSet(BaseModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = Organisation.objects.all().order_by("name")
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == "list":
            return OrganisationListSerializer
        return OrganisationSerializer

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
        confirmed = request.data.get("confirmed") == "True"

        organisation_object.assign_user(
            user=user_object,
            security_group=group_object,
            confirmed=confirmed,
        )

        user_object.groups.add(group_object)
        return Response(
            OrganisationSerializer(
                instance=organisation_object, fields=["organisationuser_set"]
            ).data
        )

    @action(
        detail=False,
        methods=["get"],
        url_name="search_by_company_name",
    )
    def search_by_company_name(self, request, *args, **kwargs):
        search_string = request.GET["company_name"]
        case_id = request.GET.get("case_id")

        # get organisations by name
        matching_organisations = self.queryset.filter(
            Q(name__icontains=search_string) | Q(companies_house_id__icontains=search_string)
        )

        # if we recieve a case_id, then exclude if organisation is already associated with the case
        if case_id:
            matching_organisations = matching_organisations.exclude(
                organisation__organisationcaserole__case=case_id,
            )

        return Response(
            OrganisationSerializer(
                instance=matching_organisations,
                many=True,
                fields=["name", "address", "post_code", "companies_house_id", "id", "case_count"],
            ).data
        )


class OrganisationCaseRoleViewSet(BaseModelViewSet):
    queryset = OrganisationCaseRole.objects.all()
    serializer_class = OrganisationCaseRoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_kwargs = {}
        if case_id := self.request.query_params.get("case_id"):
            filter_kwargs["case_id"] = case_id
        if organisation_id := self.request.query_params.get("organisation_id"):
            filter_kwargs["organisation_id"] = organisation_id

        if filter_kwargs:
            return queryset.filter(**filter_kwargs)
        return queryset


class OrganisationMergeRecordViewSet(BaseModelViewSet):
    queryset = OrganisationMergeRecord.objects.all()
    serializer_class = OrganisationMergeRecordSerializer

    def _apply_selections(self, parent_organisation, child_organisation):
        pass

    @action(
        detail=True,
        methods=["post"],
        url_name="merge_organisations",
    )
    def merge_organisations(self, request, *args, **kwargs):
        print("asd")

    @action(
        detail=True,
        methods=["get"],
        url_name="get_draft_merged_organisation",
    )
    def get_draft_merged_organisation(self, request, *args, **kwargs):
        class DraftOrganisationCreatedException(Exception):
            pass

        merge_record = self.get_object()
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        try:
            with transaction.atomic():
                # creating a savepoint here so that we can roll-back
                draft_organisation = Organisation()
                for potential_duplicate_organisation in merge_record.duplicate_organisations.all():
                    for field in potential_duplicate_organisation.parent_fields:
                        setattr(
                            draft_organisation,
                            field,
                            getattr(merge_record.parent_organisation, field),
                        )
                    for field in potential_duplicate_organisation.child_fields:
                        setattr(
                            draft_organisation,
                            field,
                            getattr(potential_duplicate_organisation.child_organisation, field),
                        )
                    Organisation.objects.merge_organisations(
                        draft_organisation,
                        potential_duplicate_organisation.child_organisation,
                        draft=False,
                    )
                # we exit this block and the changes are committed to the database, allowing the
                # serializer to read the draft organisation from the DB
                serializer_data = OrganisationSerializer(
                    instance=draft_organisation,
                    exclude=["organisationuser_set", "user_cases"],
                ).data

                # now we raise an exception, which will roll-back the transaction and delete
                # the draft organisation along with any merge changes
                raise DraftOrganisationCreatedException()
        except DraftOrganisationCreatedException:
            return Response(serializer_data)


class DuplicateOrganisationMergeViewSet(BaseModelViewSet):
    queryset = DuplicateOrganisationMerge.objects.all()
    serializer_class = DuplicateOrganisationMergeSerializer
