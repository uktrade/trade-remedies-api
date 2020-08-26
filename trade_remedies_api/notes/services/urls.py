from django.urls import path
from .api import NoteAPIView

urlpatterns = [
    path("case/<uuid:case_id>/", NoteAPIView.as_view()),
    path("case/<uuid:case_id>/<uuid:note_id>/", NoteAPIView.as_view()),
    path("case/<uuid:case_id>/on/<content_type>/<uuid:model_id>/", NoteAPIView.as_view()),
    path("case/<uuid:case_id>/on/<content_type>/<uuid:model_id>/add/", NoteAPIView.as_view()),
    path(
        "case/<uuid:case_id>/on/<content_type>/<uuid:model_id>/<str:model_key>/",
        NoteAPIView.as_view(),
    ),
    path("case/<uuid:case_id>/<uuid:note_id>/document/<uuid:document_id>/", NoteAPIView.as_view()),
]
