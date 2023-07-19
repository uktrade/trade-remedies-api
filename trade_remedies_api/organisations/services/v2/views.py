from django.contrib.auth.models import Group
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from cases.models import Submission
from config.viewsets import BaseModelViewSet
from core.models import User
from organisations.decorators import no_commit_transaction
from organisations.models import (
    DuplicateOrganisationMerge,
    Organisation,
    OrganisationMergeRecord,
    SubmissionOrganisationMergeRecord,
)
from organisations.services.v2.serializers import (
    DuplicateOrganisationMergeSerializer,
    OrganisationCaseRoleSerializer,
    OrganisationMergeRecordSerializer,
    OrganisationSerializer,
    OrganisationUserSerializer,
    SubmissionOrganisationMergeRecordSerializer,
)
from security.models import OrganisationCaseRole, OrganisationUser


class OrganisationViewSet(BaseModelViewSet):
    """
    ModelViewSet for interacting with user objects via the API.
    """

    queryset = Organisation.objects.all().order_by("name")
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
        exclude_id = request.GET.get("exclude_id")

        queryset = self.get_queryset()

        # get organisations by name
        matching_organisations = queryset.filter(
            Q(name__icontains=search_string) | Q(companies_house_id__icontains=search_string)
        )

        # if we recieve a case_id, then exclude if organisation is already associated with the case
        if case_id:
            matching_organisations = matching_organisations.exclude(
                organisation__organisationcaserole__case=case_id,
            )

        if exclude_id:
            # if we are passed an exclude_id in the request.GET,
            # then exclude the organisation with that ID from the results.
            # used in cases where there are 2 autocompletes on one page
            matching_organisations = matching_organisations.exclude(id=exclude_id)

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
        url_name="get_organisation_card_data",
        url_path="get_organisation_card_data",
    )
    def get_organisation_card_data(self, request, *args, **kwargs):
        """Returns all the data required to render the organisation card for a specific organisation.

        This is quite a costly operation and so it makes sense to keep it in its own method so:

        1. The normal OrganisationSerializer isn't slowed down by this expensive operation
        2. The address card can be rendered on the fly without having to make a separate request
        3. Changes to what is displayed in the organisation card can just be done in one place
        """
        organisation_object = self.get_object()
        return Response(organisation_object.organisation_card_data())


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


class OrganisationUserViewSet(BaseModelViewSet):
    queryset = OrganisationUser.objects.all()
    serializer_class = OrganisationUserSerializer


class OrganisationMergeRecordViewSet(BaseModelViewSet):
    queryset = OrganisationMergeRecord.objects.all()
    serializer_class = OrganisationMergeRecordSerializer

    def retrieve(self, request, *args, **kwargs):
        """We want to create merge records if someone tries to request one for an organisation that
        has not been scanned for duplicates yet."""
        organisation_object = get_object_or_404(Organisation, pk=kwargs["pk"])
        instance = organisation_object.find_potential_duplicate_orgs(
            fresh=True if request.GET.get("fresh", "no") == "yes" else False
        )

        if submission_id := request.GET.get("submission_id"):
            # Add the submission to the merge record
            submission_object = get_object_or_404(Submission, pk=submission_id)
            SubmissionOrganisationMergeRecord.objects.get_or_create(
                submission=submission_object,
                organisation_merge_record=instance,
            )
        return Response(
            OrganisationMergeRecordSerializer(
                instance=instance,
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_name="merge_organisations",
    )
    def merge_organisations(self, request, *args, **kwargs):
        merge_record = self.get_object()
        merged_organisation = merge_record.merge_organisations(
            notify_users=True, create_audit_log=True
        )
        return Response(OrganisationSerializer(merged_organisation, fields=["id"]).data)

    @action(
        detail=True,
        methods=["get"],
        url_name="get_draft_merged_selections",
    )
    @no_commit_transaction
    def get_draft_merged_selections(self, request, *args, **kwargs):
        """
        Returns a serialized draft organisation that just contains the selected attributes by the
        caseworkers in the merge process. This is used to preview the result of the first stage of
        the merge process (without viewing merged orgs users/cases/rejections etc).
        without actually committing the merge to the database.
        """
        merge_record = self.get_object()
        return_data = {}
        phantom_organisation = merge_record.parent_organisation
        for potential_duplicate_organisation in merge_record.duplicate_organisations.filter(
            status="attributes_selected"
        ).all():
            # going through the potential duplicates and applying the attributes from each
            # duplicate selected by the caseworkers to the draft organisation
            potential_duplicate_organisation._apply_selections(
                organisation=phantom_organisation,
            )
        return_data["phantom_organisation_serializer"] = OrganisationSerializer(
            phantom_organisation
        ).data

        # if we have a current_duplicate_id query parameter, we want to also get the
        # identical fields between the phantom org and the current duplicate being
        # analysed
        if current_duplicate_id := request.GET.get("current_duplicate_id"):
            current_duplicate = merge_record.duplicate_organisations.get(pk=current_duplicate_id)
            return_data["identical_fields"] = phantom_organisation.get_identical_fields(
                current_duplicate.child_organisation
            )

        return Response(return_data)

    @action(
        detail=True,
        methods=["get"],
        url_name="get_draft_merged_organisation",
    )
    @no_commit_transaction
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

        merge_record = self.get_object()
        phantom_organisation = merge_record.merge_organisations(
            organisation=merge_record.parent_organisation
        )
        return_data = phantom_organisation.organisation_card_data()
        return Response(return_data)

    @action(
        detail=True,
        methods=["patch"],
        url_name="reset",
    )
    def reset(self, request, *args, **kwargs):
        """Resets all potential duplicates of this merge to their virgin state"""
        instance = self.get_object()
        instance.duplicate_organisations.update(status="pending", child_fields=[], parent_fields=[])
        return self.retrieve(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["get"],
        url_name="get_duplicate_cases",
    )
    def get_duplicate_cases(self, request, *args, **kwargs):
        """Gets all cases that are shared by the duplicate organisations of
        this merge record including the parent organisation."""
        instance = self.get_object()
        parent_organisation_case_roles = OrganisationCaseRole.objects.filter(
            organisation=instance.parent_organisation
        ).exclude(role__key__in=["preparing", "awaiting_approval"])
        child_organisation_case_roles = OrganisationCaseRole.objects.filter(
            organisation_id__in=instance.duplicate_organisations.filter(
                status="attributes_selected"
            ).values_list("child_organisation_id", flat=True)
        )
        conflicting_org_case_roles = []

        for org_case_role in parent_organisation_case_roles:
            different_child_org_case_roles = child_organisation_case_roles.filter(
                case=org_case_role.case
            ).exclude(
                Q(role=org_case_role.role) | Q(role__key__in=["preparing", "awaiting_approval"])
            )
            if different_child_org_case_roles.exists():
                conflicting_org_case_roles.append(
                    {
                        "case_id": org_case_role.case.id,
                        "role_ids": [str(each.id) for each in different_child_org_case_roles]
                        + [str(org_case_role.id)],
                    }
                )

        return Response(data=conflicting_org_case_roles)

    @action(
        detail=False,
        methods=["get"],
        url_name="adhoc_merge",
        url_path="adhoc_merge",
    )
    def adhoc_merge(self, request, *args, **kwargs):
        """
        Create a locked OrganisationMergeRecord object for the two given organisations. This is used
        when a user wants to merge two organisations that are not flagged as duplicates.

        The resulting OrganisationMergeRecord is locked and will not be updated whenever the DB
        is searched for existing duplicates
        """
        organisation_1_id = request.GET["organisation_1_id"]
        organisation_2_id = request.GET["organisation_2_id"]

        # deleting any existing merge records for these organisations. This adhoc merge will create
        #
        OrganisationMergeRecord.objects.filter(
            Q(parent_organisation_id=organisation_1_id)
            | Q(parent_organisation_id=organisation_2_id)
        ).delete()

        organisation_merge_record_object = OrganisationMergeRecord.objects.create(
            parent_organisation_id=organisation_1_id,
            locked=True,
            status="duplicates_found",
        )
        DuplicateOrganisationMerge.objects.create(
            merge_record=organisation_merge_record_object,
            child_organisation_id=organisation_2_id,
            status="confirmed_duplicate",
        )

        return Response(
            OrganisationMergeRecordSerializer(
                instance=organisation_merge_record_object,
            ).data
        )


class DuplicateOrganisationMergeViewSet(BaseModelViewSet):
    queryset = DuplicateOrganisationMerge.objects.all()
    serializer_class = DuplicateOrganisationMergeSerializer


class SubmissionOrganisationMergeRecordViewSet(BaseModelViewSet):
    queryset = SubmissionOrganisationMergeRecord.objects.all()
    serializer_class = SubmissionOrganisationMergeRecordSerializer

    def get_object(self):
        return get_object_or_404(
            SubmissionOrganisationMergeRecord,
            submission_id=self.kwargs["pk"],
            organisation_merge_record_id__parent_organisation=self.request.GET["organisation_id"],
        )

    def retrieve(self, request, *args, **kwargs):
        submission_object = get_object_or_404(Submission, pk=kwargs["pk"])
        organisation_object = get_object_or_404(Organisation, pk=request.GET["organisation_id"])
        merge_record = organisation_object.find_potential_duplicate_orgs()

        instance, _ = SubmissionOrganisationMergeRecord.objects.get_or_create(
            submission=submission_object,
            organisation_merge_record=merge_record,
        )

        return Response(
            SubmissionOrganisationMergeRecordSerializer(
                instance=instance,
            ).data
        )
