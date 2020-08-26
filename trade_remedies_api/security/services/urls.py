from django.urls import path
from .api import CaseRolesAPI, RepresentingAPI


urlpatterns = [
    path("roles/", CaseRolesAPI.as_view()),
    path("role/<role_id>/", CaseRolesAPI.as_view()),
    path("representing/", RepresentingAPI.as_view()),
    path("representing/<uuid:organisation_id>/", RepresentingAPI.as_view()),
]
