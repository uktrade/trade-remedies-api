from django.urls import path
from .api import TaskAPIView

urlpatterns = [
    path("", TaskAPIView.as_view()),
    path("<uuid:task_id>/", TaskAPIView.as_view()),
    path("case/<uuid:case_id>/on/<content_type>/<uuid:model_id>/", TaskAPIView.as_view()),
]
