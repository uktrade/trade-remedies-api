from cases.models import Submission
from django.db.models.functions import TruncDate
from django.db.models import Count
from django.db import connection
from reports.queries.registry import register_report

STATUS_DRAFT = 19
STATUS_RECEIVED = 20
SUBMISSION_TYPE = 7


def roi_by_date():
    """
    Registrations of interest by date submitted and received.
    """
    draft_submissions = (
        Submission.objects.filter(type=SUBMISSION_TYPE, status=STATUS_DRAFT,)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Count("id"))
        .values("date", "total")
        .order_by("date")
    )

    data = [
        {"date": draft["date"].strftime("%Y-%m-%d"), "total": draft["total"], "status": "Draft"}
        for draft in draft_submissions
    ]

    RECEIVED_SQL = f"""
    SELECT date_trunc('day', audit.created_at) as date, COUNT(*) as total
    FROM cases_submission sub JOIN  audit_audit audit ON sub.id = audit.model_id
    WHERE sub.type_id = {SUBMISSION_TYPE}
    AND sub.status_id = {STATUS_RECEIVED}
    AND audit.type = 'UPDATE'
    AND audit.data->'status'->'from' = '{STATUS_DRAFT}'
    AND audit.data->'status'->'to'->'id' = '{STATUS_RECEIVED}'
    GROUP BY date;
    """
    with connection.cursor() as cursor:
        cursor.execute(RECEIVED_SQL)
        rows = cursor.fetchall()

    data += [
        {"date": row[0].strftime("%Y-%m-%d"), "total": row[1], "status": "Received"} for row in rows
    ]
    return data


register_report(roi_by_date)
