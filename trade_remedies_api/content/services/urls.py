from django.urls import path, re_path
from .api import ContentAPIView

urlpatterns = [
    path("", ContentAPIView.as_view()),
    path("<uuid:content_id>/", ContentAPIView.as_view()),
]
