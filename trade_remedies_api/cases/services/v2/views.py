from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from audit import AUDIT_TYPE_CREATE, AUDIT_TYPE_UPDATE
from audit.utils import audit_log
from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Case, Submission, SubmissionType
from cases.services.v2.serializers import (
    CaseSerializer,
    SubmissionSerializer,
    SubmissionTypeSerializer,
)
from config.viewsets import BaseModelViewSet
from organisations.models import Organisation
from security.constants import ROLE_PREPARING
from security.models import CaseRole, OrganisationCaseRole


class CaseViewSet(BaseModelViewSet):
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def get_queryset(self):
        if self.request.query_params.get("open_to_roi"):
            # We only want the cases which are open to registration of interest applications
            return Case.objects.available_for_regisration_of_intestest(self.request.user)
        return super().get_queryset()


class SubmissionViewSet(BaseModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer

    @action(detail=True, methods=["put"], url_name="update_submission_status")
    def update_submission_status(self, request, *args, **kwargs):
        """Updates the status of a submission object.

        Deals with sending any notifications that need to happen if a status is changed, and also
        updating any timestamp fields on the submission where necessary.
        """
        submission_object = self.get_object()
        new_status = request.data["new_status"]
        submission_object.update_status(new_status, request.user)

        audit_log(
            audit_type=AUDIT_TYPE_UPDATE,
            user=request.user,
            model=submission_object,
            case=submission_object.case,
            data={
                "message": f"Submission {submission_object.id} status updated to {new_status}",
            },
        )

        return self.retrieve(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @transaction.atomic
    @action(detail=True, methods=["put"], url_name="add_organisation_to_registration_of_interest")
    def add_organisation_to_registration_of_interest(self, request, *args, **kwargs):
        """Adds an Organisation object to a ROI submission.

        Requires an organisation_id in the request.POST and an optional contact_id to specify
        which contact should be made primary contact between the organisation and case."""
        from django_restql.mixins import RequestQueryParserMixin

        organisation_object = get_object_or_404(Organisation, pk=request.data["organisation_id"])
        submission_object = self.get_object()
        try:
            previous_organisation_object = submission_object.contact.organisation
        except AttributeError:
            previous_organisation_object = None
        parsed_query = RequestQueryParserMixin.get_parsed_restql_query_from_req(request)

        # Checking if a ROI already exists for this organisation and case
        existing_roi = Submission.objects.filter(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            case=submission_object.case,
            organisation=organisation_object,
            status__locking=True,
        ).exclude(id=submission_object.id)
        if existing_roi:
            # If it does, we return a 409 with the serialized ROI that already exists
            return Response(
                status=409,
                data=self.serializer_class(existing_roi, many=True, parsed_query=parsed_query).data,
            )

        # Always use the requesting user's contact object, as that is the person actually
        # registering interest, we need to associate them with the submission. The other contact
        # that is created as part of the ROI journey is just associated with the organisation and
        # can be invited at a future date
        contact_object = request.user.contact
        contact_object.set_primary(
            case=submission_object.case,
            organisation=organisation_object,
            request_by=self.request.user,
        )

        # Removing the previous organisation from the case if they are not properly enrolled
        if organisation_object != previous_organisation_object:
            OrganisationCaseRole.objects.filter(
                organisation=previous_organisation_object,
                case=submission_object.case,
                role=CaseRole.objects.get(id=ROLE_PREPARING),
            ).delete()

            # Associating the organisation with the case
            OrganisationCaseRole.objects.get_or_create(
                organisation=organisation_object,
                case=submission_object.case,
                defaults={
                    "role": CaseRole.objects.get(id=ROLE_PREPARING),
                    "sampled": True,
                    "created_by": request.user,
                },
            )

        # Deleting all the user SubmissionDocument objects as they no longer apply to the submission
        # only if the new organisation is different from the previous
        if organisation_object != previous_organisation_object:
            submission_object.submissiondocument_set.filter(
                type__key__in=["respondent", "loa"]
            ).delete()

        submission_object.organisation = organisation_object
        submission_object.contact = contact_object
        submission_object.modified_by = request.user
        submission_object.save()

        audit_message = f"Submission {submission_object.id} given to org {organisation_object.id}"
        if previous_organisation_object:
            audit_message += f" from {previous_organisation_object.pk}"

        audit_log(
            audit_type=AUDIT_TYPE_UPDATE,
            user=request.user,
            model=submission_object,
            case=submission_object.case,
            data={
                "message": audit_message,
                "contact": contact_object.pk,
            },
        )

        return Response(
            self.serializer_class(instance=submission_object, parsed_query=parsed_query).data
        )

    def perform_create(self, serializer):
        created_submission = super().perform_create(serializer)
        audit_log(
            audit_type=AUDIT_TYPE_CREATE,
            user=created_submission.created_by,
            model=created_submission,
            case=created_submission.case,
        )
        return created_submission


class SubmissionTypeViewSet(BaseModelViewSet):
    queryset = SubmissionType.objects.all()
    serializer_class = SubmissionTypeSerializer
