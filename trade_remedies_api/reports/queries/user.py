from core.models import User
from django.db.models.functions import TruncDate
from django.db.models import Count
from reports.queries.registry import register_report
from security.constants import SECURITY_GROUPS_PUBLIC


def users_by_date():
    """
    User registration count broken by date
    """
    users = (
        User.objects.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Count("id"))
        .values("date", "total")
        .order_by("date")
    )
    data = [{"date": user["date"].strftime("%Y-%m-%d"), "total": user["total"]} for user in users]
    return data


def total_public_users():
    """
    Total public users
    """
    total_users = User.objects.filter(
        groups__name__in=SECURITY_GROUPS_PUBLIC, deleted_at__isnull=True,
    ).count()
    total_verified = User.objects.filter(
        groups__name__in=SECURITY_GROUPS_PUBLIC,
        userprofile__email_verified_at__isnull=False,
        deleted_at__isnull=True,
    ).count()
    data = [{"total": total_users, "type": "all"}, {"total": total_verified, "type": "verified",}]
    return data


register_report(users_by_date)
register_report(total_public_users)
