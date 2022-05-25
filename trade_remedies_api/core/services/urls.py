from django.urls import path
from .api import (
    FeatureFlagApiView,
    SystemParameterApiView,
    NotificationTemplateAPI,
    JobTitlesView,
    FeedbackExport,
    ValidationErrorAPIView,
)
from .ch_proxy import CompaniesHouseApiSearch


urlpatterns = [
    path("systemparam/", SystemParameterApiView.as_view()),
    path("feature-flags/<str:key>/", FeatureFlagApiView.as_view()),
    path("notification/template/<str:template_key>/", NotificationTemplateAPI.as_view()),
    path("jobtitles/", JobTitlesView.as_view()),
    path("search/", CompaniesHouseApiSearch.as_view()),
    path("feedback/export/<uuid:form_id>/", FeedbackExport.as_view()),
    path("validation_error/<str:key>/", ValidationErrorAPIView.as_view()),
]
