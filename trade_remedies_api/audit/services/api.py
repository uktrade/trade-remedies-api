from core.services.base import TradeRemediesApiView, ResponseSuccess
from django.http import HttpResponse
from audit import AUDIT_TYPE_DELIVERED
from audit.models import Audit
from audit.utils import get_notify_fail_report
from cases.models import get_case
from core.constants import TRUTHFUL_INPUT_VALUES
from core.exporters import QuerysetExporter
import mimetypes


mimetypes.init()


class AuditTrailView(TradeRemediesApiView):
    """Return an audit trail.

    View to return some or all audit trail items.
    """

    def get(self, request, case_id=None, *args, **kwargs):
        """Get audit trail.

        Get all audit trail items paginated and in chronological order in order.
        Optionally limit response to:
        - items for a given case if case_id specified in url.
        - items for a given audit type if `type` query param specified.
        - items for given milestone if `milestone` query param specified.

        :param (HTTPRequest) request: request object.
        :param (str) case_id: Optional case id to limit response.
        :returns (HTTPResponse): Audit trail items dependent on request.
        """
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
    """Generate an audit trail export."""

    @staticmethod
    def get(request, case_id, *args, **kwargs):
        """Get audit trail export for a case.

        Generates an export file in the desired format (if specified in `format`
        query param). Supported formats are specified in `QuerysetExport.FILE_FORMATS`.

        :param (HTTPRequest) request: request object.
        :param (str) case_id: case id to filter report on.
        :returns (HTTPResponse): Audit trail export file in requested format (if specified).
          Default is `xlsx`.
        """
        file_format = request.query_params.get("format", "xlsx")
        audit_trail = Audit.objects.filter(case_id=case_id).order_by("created_at").iterator()
        export = QuerysetExporter(
            queryset=audit_trail, file_format=file_format, prefix="tr-audit-export"
        )
        export_file = export.do_export(compatible=True)
        mime_type = mimetypes.guess_type(export_file.name, False)[0]
        response = HttpResponse(export_file.read(), content_type=mime_type)
        response["Content-Disposition"] = f"attachment; filename={export_file.name}"
        return response


class NotifyAuditReport(TradeRemediesApiView):
    """Notification failure management.

    Enables client to get a report of failed notifications logged in the audit trail,
    and update the audit log item with an acknowledgement of the failure.
    """

    @staticmethod
    def get(request, case_id=None):
        """Return all unacknowledged notify failures for a case.

        Generates report document with additional detail (if specified in `detail`
        query param).

        :param (HTTPRequest) request: request object.
        :param (str) case_id: case to report on.
        :returns (HTTPResponse): Document containing failed notifications logged
          in the audit trail.
        """
        detail = request.query_params.get("detail")
        case = get_case(case_id)
        report = get_notify_fail_report(case=case, detail=bool(detail))
        return ResponseSuccess({"result": report})

    def post(self, request, case_id=None, audit_id=None):
        """Acknowledge notify failures for a given audit item.

        Updates a particular audit log item indicating a notification failure is
        considered acknowledged.

        :param (HTTPRequest) request: request object.
        :param (str) case_id: related case.
        :param (str) audit_id: related audit entry.
        :returns (HTTPResponse): Document containing outstanding failed audit
          notifications logged in the audit trail.
        """
        audit = Audit.objects.filter(id=audit_id, case_id=case_id, type=AUDIT_TYPE_DELIVERED)
        audit.data["ack"] = True
        audit.save()
        return self.get(request, case_id=case_id)


from audit.tasks import check_notify_send_status


def test_notify(request):
    check_notify_send_status()