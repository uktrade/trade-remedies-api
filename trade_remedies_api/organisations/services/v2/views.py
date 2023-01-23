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

    @action(
        detail=True,
        methods=["get"],
        url_name="find_similar_organisations",
        url_path="find_similar_organisations",
    )
    def find_similar_organisations(self, request, *args, **kwargs):
        organisation = self.get_object()
        return Response(
            OrganisationMergeRecordSerializer(
                instance=organisation.find_potential_duplicate_orgs(),
            ).data
        )

    @action(
        detail=True,
        methods=["get"],
        url_name="has_similar_organisations",
        url_path="has_similar_organisations",
    )
    def has_similar_organisations(self, request, *args, **kwargs):
        organisation = self.get_object()
        return Response(len(organisation.find_potential_duplicate_orgs().potential_duplicates))


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

    def retrieve(self, request, *args, **kwargs):
        """We want to create merge records if someone tries to request one for an organisation that
        has not been scanned for duplicates yet."""
        instance = self.get_object()
        return Response(
            OrganisationMergeRecordSerializer(
                instance=instance,
                fields=["organisation", "potential_duplicates"],
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_name="merge_organisations",
    )
    def merge_organisations(self, request, *args, **kwargs):
        merge_record = self.get_object()
        merged_organisation = merge_record.merge_organisations()
        return Response(OrganisationSerializer(merged_organisation).data)

    @action(
        detail=True,
        methods=["get"],
        url_name="get_draft_merged_organisation",
    )
    def get_draft_merged_organisation(self, request, *args, **kwargs):
        """
        Returns a draft organisation that is the result of merging the child organisation into
        the parent organisation using the selected attributes. The draft organisation is never
        actually committed to the database, it is only used to preview the result of the merge
        using the OrganisationSerializer.

        Returns
        -------
        Serialized draft organisation
        """
        class DraftOrganisationCreatedException(Exception):
            pass

        merge_record = self.get_object()
        cursor = connection.cursor()
        # setting the read level to REPEATABLE READ ensures that we can read the uncommitted data
        # from the database when loading the serializer
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        try:
            # running it with transaction.atomic() so that changes are stored in a single
            # transaction, but not committed to the database
            with transaction.atomic():
                # the phantom_organisation never exists in the database, it is only used to
                # preview the result of the merge
                # 👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻
                phantom_organisation = Organisation()
                # 👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻👻
                phantom_organisation = merge_record.merge_organisations(
                    organisation=phantom_organisation
                )

                serializer_data = OrganisationSerializer(
                    instance=phantom_organisation,
                    exclude=["organisationuser_set", "user_cases"],
                ).data

                # now we raise an exception, which will roll back the transaction and delete
                # the draft organisation along with any merge changes
                raise DraftOrganisationCreatedException()
        except DraftOrganisationCreatedException:
            return Response(serializer_data)


class DuplicateOrganisationMergeViewSet(BaseModelViewSet):
    queryset = DuplicateOrganisationMerge.objects.all()
    serializer_class = DuplicateOrganisationMergeSerializer
