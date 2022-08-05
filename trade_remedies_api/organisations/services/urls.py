from django.conf import settings
from django.urls import path
from rest_framework import routers

from .api import (
    DuplicateOrganisationsAPI,
    OrganisationApprovalNotifyAPI,
    OrganisationCaseRoleAPI,
    OrganisationCaseSampleToggleAPI,
    OrganisationContactsAPI,
    OrganisationLookupAPI,
    OrganisationMatchingAPI,
    OrganisationNonResponsiveToggleAPI,
    OrganisationRejectAPI,
    OrganisationUserCaseAPI,
    OrganisationUsersAPI,
    OrganisationsAPIView,
    SubmissionApprovalNotifyAPI,
)
from .v2.views import OrganisationViewSet

urlpatterns = [
    path("", OrganisationsAPIView.as_view()),
    path("<uuid:organisation_id>/", OrganisationsAPIView.as_view()),
    path("<uuid:organisation_id>/users/", OrganisationUsersAPI.as_view()),
    path("<uuid:organisation_id>/user/<uuid:user_id>/", OrganisationUsersAPI.as_view()),
    path(
        "<uuid:organisation_id>/user/<uuid:user_id>/set/admin/",
        OrganisationUsersAPI.as_view(toggle_admin=True),
    ),
    path("<uuid:organisation_id>/contacts/", OrganisationContactsAPI.as_view()),
    path("<uuid:organisation_id>/case/<uuid:case_id>/", OrganisationsAPIView.as_view()),
    path(
        "case/<uuid:case_id>/<str:organisation_type>/organisation/", OrganisationsAPIView.as_view()
    ),
    path(
        "case/<uuid:case_id>/<str:organisation_type>/organisation/<uuid:organisation_id>/",
        OrganisationsAPIView.as_view(),
    ),
    path("case/<uuid:case_id>/", OrganisationsAPIView.as_view()),
    path(
        "<uuid:organisation_id>/case/<uuid:case_id>/sampled/",
        OrganisationCaseSampleToggleAPI.as_view(),
    ),
    path(
        "<uuid:organisation_id>/case/<uuid:case_id>/nonresponsive/",
        OrganisationNonResponsiveToggleAPI.as_view(),
    ),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/notify/<str:action>/",
        OrganisationApprovalNotifyAPI.as_view(),
    ),
    path("submission/<uuid:submission_id>/approval/", SubmissionApprovalNotifyAPI.as_view()),
    path(
        "<uuid:organisation_id>/case/<uuid:case_id>/role/<str:role_key>/",
        OrganisationCaseRoleAPI.as_view(),
    ),
    path(
        "<uuid:organisation_id>/case/<uuid:case_id>/verify/",
        OrganisationCaseRoleAPI.as_view(verify=True),
    ),
    path("<uuid:organisation_id>/case/<uuid:case_id>/remove/", OrganisationCaseRoleAPI.as_view()),
    path("<uuid:organisation_id>/matches/", OrganisationMatchingAPI.as_view()),
    path("matches/", OrganisationMatchingAPI.as_view()),
    path("<uuid:organisation_id>/user_cases/", OrganisationUserCaseAPI.as_view()),
    path("<uuid:organisation_id>/reject/", OrganisationRejectAPI.as_view()),
    path("dedupe/", DuplicateOrganisationsAPI.as_view()),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/loa/",
        OrganisationCaseRoleAPI.as_view(post_type="loa"),
    ),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/",
        OrganisationCaseRoleAPI.as_view(),
    ),
    path("lookup/", OrganisationLookupAPI.as_view()),
]
