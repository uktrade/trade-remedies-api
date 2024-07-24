from django.urls import path
from rest_framework import routers

from .api import (
    FeatureFlagApiView,
    SystemParameterApiView,
    NotificationTemplateAPI,
    JobTitlesView,
    ValidationErrorAPIView,
)
from .ch_proxy import CompaniesHouseApiSearch
from core.services.v2.feature_flags.views import FlagViewSet

urlpatterns = [
    path("systemparam/", SystemParameterApiView.as_view()),
    path("notification/template/<str:template_key>/", NotificationTemplateAPI.as_view()),
    path("feature-flags/<str:key>/", FeatureFlagApiView.as_view()),
    path("jobtitles/", JobTitlesView.as_view()),
    path("search/", CompaniesHouseApiSearch.as_view()),
    path("validation_error/<str:key>/", ValidationErrorAPIView.as_view()),
]

router = routers.SimpleRouter()
router.register("django-feature-flags", FlagViewSet, basename="django-feature-flags")

urlpatterns += router.urls
