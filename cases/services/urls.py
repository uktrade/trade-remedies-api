from django.urls import path
from django.views.decorators.cache import cache_page
from django.conf import settings
from .api import (
    CasesAPIView,
    CaseInitiationAPIView,
    SubmissionsAPIView,
    ProductsAPIView,
    ProductHSCodeAPI,
    ExportSourceAPIView,
    ApplicationStateAPIView,
    RequestReviewAPIView,
    TemplateDownloadAPIView,
    DocumentDownloadAPIView,
    SubmissionStatusAPIView,
    SubmissionCloneAPIView,
    SubmissionNotifyAPI,
    CaseStatusAPI,
    CaseWorkflowAPI,
    CaseEnumsAPI,
    CaseUserAssignAPI,
    CaseInterestAPI,
    CaseOrganisationsAPIView,
    CaseUsersAPI,
    SubmissionTypeAPI,
    SubmissionDocumentStatusAPI,
    ThirdPartyInvitesAPI,
    SubmissionDocumentsAPI,
    SubmissionOrganisationAPI,
    PublicCaseView,
    PublicNoticeView,
    CaseStateAPI,
    CasesCountAPIView,
    CaseParticipantsAPI,
    SubmissionExistsAPI,
    CaseMilestoneDatesAPI,
    CaseReviewTypesAPI,
    ReviewTypeAPIView,
    NoticesAPI,
)

urlpatterns = [
    path("", CasesAPIView.as_view()),
    path("count/", CasesCountAPIView.as_view()),
    path("user/<uuid:user_id>/", CasesAPIView.as_view()),
    path("enums/", cache_page(60 * settings.API_CACHE_TIMEOUT)(CaseEnumsAPI.as_view())),
    path("enums/<uuid:case_id>/", CaseEnumsAPI.as_view()),
    path("<uuid:case_id>/", CasesAPIView.as_view()),
    path("<str:case_number>/public/", PublicCaseView.as_view()),
    path("<uuid:case_id>/state/", CaseStateAPI.as_view()),
    path("state/", CaseStateAPI.as_view()),
    path("publicnotices/", PublicNoticeView.as_view()),
    path("initiate/", CaseInitiationAPIView.as_view()),
    path("interest/", CaseInterestAPI.as_view()),
    path("interest/<uuid:case_id>/", CaseInterestAPI.as_view()),
    path("notices/", NoticesAPI.as_view()),
    path("notice/", NoticesAPI.as_view()),
    path("notice/<uuid:notice_id>/", NoticesAPI.as_view()),
    path("<uuid:case_id>/participants/", CaseParticipantsAPI.as_view()),
    path("organisation/<uuid:organisation_id>/invites/", ThirdPartyInvitesAPI.as_view()),
    path("<uuid:case_id>/invites/", ThirdPartyInvitesAPI.as_view()),
    path("submission_type/<int:submission_type_id>/", SubmissionTypeAPI.as_view()),
    path("organisation/<uuid:organisation_id>/", CasesAPIView.as_view()),
    path("organisation/<uuid:organisation_id>/all/", CasesAPIView.as_view(all_cases=True)),
    path("<uuid:case_id>/organisation/<uuid:organisation_id>/", CasesAPIView.as_view()),
    path("<uuid:case_id>/status/", CaseStatusAPI.as_view()),
    path("<uuid:case_id>/users/", CaseUsersAPI.as_view()),
    path("<uuid:case_id>/organisations/", CaseOrganisationsAPIView.as_view()),
    path("<uuid:case_id>/milestones/", CaseMilestoneDatesAPI.as_view()),
    path("<uuid:case_id>/milestone/<str:milestone_key>/", CaseMilestoneDatesAPI.as_view()),
    path("<uuid:case_id>/reviewtypes/", CaseReviewTypesAPI.as_view()),
    # Submission
    path("<uuid:case_id>/submissions/", SubmissionsAPIView.as_view()),
    path("<uuid:case_id>/submissions/global/", SubmissionsAPIView.as_view(show_global=True)),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submissions/",
        SubmissionsAPIView.as_view(),
    ),
    path("<uuid:case_id>/submission/<uuid:submission_id>/", SubmissionsAPIView.as_view()),
    path(
        "<uuid:case_id>/submission/<uuid:submission_id>/documents/",
        SubmissionDocumentsAPI.as_view(),
    ),
    path(
        "<uuid:case_id>/submission/<uuid:submission_id>/documents/for/<uuid:organisation_id>/",
        SubmissionDocumentsAPI.as_view(),
    ),
    path(
        "<uuid:case_id>/submission/<uuid:submission_id>/organisation/",
        SubmissionOrganisationAPI.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/",
        SubmissionsAPIView.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/notify/<str:notice_type>/",
        SubmissionNotifyAPI.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/status/",
        SubmissionStatusAPIView.as_view(),
    ),
    path(
        "<uuid:case_id>/submission/<uuid:submission_id>/status/", SubmissionStatusAPIView.as_view()
    ),
    path("<uuid:case_id>/submission/<uuid:submission_id>/clone/", SubmissionCloneAPIView.as_view()),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/"
        "<uuid:submission_id>/document/<uuid:document_id>/download/",
        DocumentDownloadAPIView.as_view(),
    ),  # TODO: Consolidate the two
    # Organisation Submissions
    # path('organisation/<uuid:organisation_id>/submissions/<int:submission_type_id>/', SubmissionsAPIView.as_view()),
    # Submission Status
    path("submission/status/", SubmissionStatusAPIView.as_view()),
    # Submission exists
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/type/<int:submission_type_id>/",
        SubmissionExistsAPI.as_view(),
    ),
    # Submission Document Status
    path(
        "<uuid:case_id>/submission/<uuid:submission_id>/document/<uuid:document_id>/status/",
        SubmissionDocumentStatusAPI.as_view(),
    ),
    # Team
    path("<uuid:case_id>/team/", CaseUserAssignAPI.as_view()),
    path("<uuid:case_id>/users/assign/", CaseUserAssignAPI.as_view()),
    # path('<uuid:case_id>/users/assign/<uuid:user_id>/', SubmissionsAPIView .as_view()),
    # Product
    path("<uuid:case_id>/organisation/<uuid:organisation_id>/product/", ProductsAPIView.as_view()),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/product/<uuid:product_id>/",
        ProductsAPIView.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/product/<uuid:product_id>/hscode/<uuid:code_id>/",
        ProductHSCodeAPI.as_view(),
    ),
    # Export Source
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/exportsource/",
        ExportSourceAPIView.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/exportsource/<uuid:export_source_id>/",
        ExportSourceAPIView.as_view(),
    ),
    path("<uuid:case_id>/submission/<uuid:submission_id>/reviewtype/", ReviewTypeAPIView.as_view()),
    # Set Review
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/review/",
        RequestReviewAPIView.as_view(),
    ),
    # Application state
    path("state/", ApplicationStateAPIView.as_view()),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/state/",
        ApplicationStateAPIView.as_view(),
    ),
    path(
        "<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/state/",
        ApplicationStateAPIView.as_view(),
    ),
    # case workflow
    path("<uuid:case_id>/workflow/", CaseWorkflowAPI.as_view()),
    # accept multiple node values
    path("<uuid:case_id>/workflow/state/", CaseWorkflowAPI.as_view()),
    # set a single node value
    path("<uuid:case_id>/workflow/value/<str:node_key>/", CaseWorkflowAPI.as_view()),
]
