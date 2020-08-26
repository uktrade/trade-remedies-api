from django.urls import path
from .views import WorkflowEditorView


urlpatterns = [
    path("editor/", WorkflowEditorView.as_view()),
]
