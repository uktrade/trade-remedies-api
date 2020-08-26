from django.urls import path
from .api import ContactsAPI, ContactPrimaryAPI, ContactLookup

urlpatterns = [
    path("", ContactsAPI.as_view()),
    path("<uuid:contact_id>/", ContactsAPI.as_view()),
    path(
        "case/<uuid:case_id>/organisation/<uuid:organisation_id>/contact/add/",
        ContactsAPI.as_view(),
    ),
    path(
        "<uuid:contact_id>/case/<uuid:case_id>/set/primary/<uuid:organisation_id>/",
        ContactPrimaryAPI.as_view(),
    ),
    path("lookup/", ContactLookup.as_view()),
]
