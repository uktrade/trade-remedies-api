from django.urls import path
from .api import (
    DocumentAPIView,
    DocumentStreamDownloadAPIView,
    DocumentIssueAPI,
    DocumentConfidentialAPI,
    CaseDocumentAPI,
    CaseDocumentCountAPI,
    DocumentBundlesAPI,
    BundleDocumentAPI,
    DocumentSearchAPI,
    DocumentSearchIndexAPI,
)

# Root path: document | documents
urlpatterns = [
    path("", DocumentAPIView.as_view()),
    # Search
    path("search/", DocumentSearchAPI.as_view()),
    path("search/case/<uuid:case_id>/", DocumentSearchAPI.as_view()),
    path("index/status/", DocumentSearchIndexAPI.as_view()),
    path("system/", DocumentAPIView.as_view(system=True)),
    path("system/<uuid:document_id>/", DocumentAPIView.as_view(system=True)),
    path("<uuid:document_id>/", DocumentAPIView.as_view()),
    path("<uuid:document_id>/download/", DocumentStreamDownloadAPIView.as_view()),
    path("case/<uuid:case_id>/bundles/", DocumentBundlesAPI.as_view()),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/",
        DocumentAPIView.as_view(),
    ),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/submission/",
        DocumentAPIView.as_view(),
    ),
    path(
        "case/<uuid:case_id>/submission/<uuid:submission_id>/document/<uuid:document_id>/",
        DocumentAPIView.as_view(),
    ),
    path("case/<uuid:case_id>/submission/<uuid:submission_id>/", DocumentAPIView.as_view()),
    path("case/<uuid:case_id>/issue/", DocumentIssueAPI.as_view()),
    path("case/<uuid:case_id>/confidential/", DocumentConfidentialAPI.as_view()),
    path("case/<uuid:case_id>/count/", CaseDocumentCountAPI.as_view()),
    path("case/<uuid:case_id>/<str:source>/", CaseDocumentAPI.as_view()),
    path("case/<uuid:case_id>/", DocumentAPIView.as_view()),
    path("case/<uuid:case_id>/document/<uuid:document_id>/", DocumentAPIView.as_view()),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/submission"
        "/<uuid:submission_id>/delete/<uuid:document_id>/",
        DocumentAPIView.as_view(),
    ),
    # Download document urls
    path(
        "organisation/<uuid:organisation_id>/download/<uuid:document_id>/",
        DocumentStreamDownloadAPIView.as_view(),
    ),
    path(
        "submission/<uuid:submission_id>/download/<uuid:document_id>/",
        DocumentStreamDownloadAPIView.as_view(),
    ),
    path(
        "organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/download/<uuid:document_id>/",
        DocumentStreamDownloadAPIView.as_view(),
    ),
    # Document bundles
    path("bundles/for/<int:case_type_id>/", DocumentBundlesAPI.as_view()),
    path("bundles/for/<int:case_type_id>/status/<str:status>/", DocumentBundlesAPI.as_view()),
    path("bundles/for/subtype/<int:submission_type_id>/", DocumentBundlesAPI.as_view()),
    path(
        "bundles/for/subtype/<int:submission_type_id>/status/<str:status>/",
        DocumentBundlesAPI.as_view(),
    ),
    path("bundles/status/<str:status>/", DocumentBundlesAPI.as_view()),
    path("bundle/", DocumentBundlesAPI.as_view(single=True)),
    path("bundle/<uuid:bundle_id>/", DocumentBundlesAPI.as_view(single=True)),
    path("bundle/<uuid:bundle_id>/documents/", DocumentAPIView.as_view()),
    path("bundle/<uuid:bundle_id>/document/<uuid:document_id>/add/", BundleDocumentAPI.as_view()),
    path(
        "bundle/<uuid:bundle_id>/document/<uuid:document_id>/remove/", BundleDocumentAPI.as_view()
    ),
]
