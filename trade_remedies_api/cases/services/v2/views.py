from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Case, Submission, SubmissionType
from cases.services.v2.serializers import CaseSerializer, SubmissionSerializer
from contacts.models import Contact
from organisations.models import Organisation
from security.constants import ROLE_PREPARING
from security.models import CaseRole, OrganisationCaseRole


class CaseViewSet(viewsets.ModelViewSet):
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def get_queryset(self):
        if self.request.query_params.get("open_to_roi"):
            # We only want the cases which are open to registration of interest applications
            return Case.objects.available_for_regisration_of_intestest(self.request.user)
        return super().get_queryset()


class SubmissionViewSet(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer

    @action(detail=True, methods=["put"], url_name="update_submission_status")
    def update_submission_status(self, request, *args, **kwargs):
        submission_object = self.get_object()
        new_status = request.data["new_status"]
        status_object = getattr(submission_object.type, f"{new_status}_status")
        submission_object.transition_status(status_object)
        return self.retrieve(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @transaction.atomic
    @action(detail=True, methods=["put"], url_name="add_organisation_to_registration_of_interest")
    def add_organisation_to_registration_of_interest(self, request, *args, **kwargs):
        organisation_object = get_object_or_404(
            Organisation,
            pk=request.data["organisation_id"]
        )
        submission_object = self.get_object()

        # Checking if a ROI already exists for this organisation and case

        if contact_id := request.data.get("contact_id", None):
            contact_object = get_object_or_404(
                Contact,
                pk=contact_id
            )
        else:
            contact_object = request.user.contact
        contact_object.set_primary(
            case=submission_object.case,
            organisation=organisation_object,
            request_by=self.request.user
        )

        # Associating the organisation with the case
        OrganisationCaseRole.objects.get_or_create(
            organisation=organisation_object,
            case=submission_object.case,
            defaults={
                "role": CaseRole.objects.get(id=ROLE_PREPARING),
                "sampled": True,
                "created_by": request.user,
            }
        )
        submission_object.organisation = organisation_object
        submission_object.modified_by = request.user
        submission_object.save()

        return Response(self.serializer_class(instance=submission_object).data)
