from core.services.base import TradeRemediesApiView, ResponseSuccess
from django.http import HttpResponse
from audit import AUDIT_TYPE_DELIVERED
from audit.models import Audit
from audit.utils import get_notify_fail_report
from cases.models import get_case
from core.constants import TRUTHFUL_INPUT_VALUES
from core.writers import QuerysetExport
import mimetypes

# initialise the mimetypes module
mimetypes.init()


class AuditTrailView(TradeRemediesApiView):
    """
    Return an audit trail

    `GET /audit/`
    Return all audit trail items, paginated and in chronological order

    `GET /audit/case/{CASE_ID}/`
    Return all audit trail for a case, paginated and in chronological order
    """

    def get(self, request, case_id=None, *args, **kwargs):
        audit_type = request.query_params.get("type")
        milestone_only = request.query_params.get("milestone") in TRUTHFUL_INPUT_VALUES
        order_by = request.query_params.get("order_by", "-created_at")
        if not audit_type and not case_id:
            audit_trail = Audit.objects.filter()
        else:
            filter_kwargs = {"case_id": case_id}
            if audit_type:
                filter_kwargs["type"] = audit_type
            if milestone_only is True:
                filter_kwargs["milestone"] = True
            audit_trail = Audit.objects.filter(**filter_kwargs)
        audit_trail = audit_trail.select_related(
            "created_by", "assisted_by", "content_type"
        ).order_by(order_by)
        limited_queryset = (
            audit_trail[self._start : self._start + self._limit] if self._limit else audit_trail
        )
        return ResponseSuccess({"results": [audit.to_dict() for audit in limited_queryset]})


class AuditTrailExport(TradeRemediesApiView):
    """
    Generate an audit trail export
    """

    def get(self, request, case_id, *args, **kwargs):
        file_format = request.query_params.get("format", "xls")
        audit_trail = Audit.objects.filter(case_id=case_id).order_by("created_at").iterator()
        export = QuerysetExport(queryset=audit_trail, file_format=file_format)
        export_file = export.do_export()
        mime_type = mimetypes.guess_type(export_file.name, False)[0]
        response = HttpResponse(export_file.read(), content_type=mime_type)
        response["Content-Disposition"] = f"attachment; filename={export.filename}"
        return response


class NotifyAuditReport(TradeRemediesApiView):
    """
    Return an audit report for Notify failures

    `GET /audit/notify/{CASE_ID}/`
    Return all unacknowledged notify failures for a case

    `POST /audit/notify/{CASE_ID}/ack/{AUDIT_ID}/`
    Acknowledge a failure to remove it from futher reports
    """

    def get(self, request, case_id=None, audit_id=None):
        detail = request.query_params.get("detail")
        case = get_case(case_id)
        report = get_notify_fail_report(case=case, detail=bool(detail))
        return ResponseSuccess({"result": report})

    def post(self, request, case_id=None, audit_id=None):
        audit = Audit.objects.filter(id=audit_id, case_id=case_id, type=AUDIT_TYPE_DELIVERED)
        audit.data["ack"] = True
        audit.save()
        return self.get(request, case_id=case_id)
