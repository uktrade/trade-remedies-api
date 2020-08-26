from django.urls import path
from .api import WorkflowTemplateAPI


urlpatterns = [
    path("templates/", WorkflowTemplateAPI.as_view()),
    path("templates/<uuid:template_id>/", WorkflowTemplateAPI.as_view()),
]
