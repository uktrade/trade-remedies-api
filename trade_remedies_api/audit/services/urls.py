from django.urls import path
from .api import (
    AuditTrailView,
    AuditTrailExport,
    NotifyAuditReport,
)

urlpatterns = [
    path("", AuditTrailView.as_view()),
    path("case/<uuid:case_id>/export/", AuditTrailExport.as_view()),
    path("case/<uuid:case_id>/", AuditTrailView.as_view()),
    path("notify/<uuid:case_id>/", NotifyAuditReport.as_view()),
    path("notify/<uuid:case_id>/ack/<uuid:audit_id>/", NotifyAuditReport.as_view()),
]
