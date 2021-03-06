import logging

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
from security.models import OrganisationCaseRole
from security.constants import (
    ROLE_AWAITING_APPROVAL,
    ROLE_PREPARING,
    ROLE_REJECTED,
    SECURITY_GROUP_TRA_ADMINISTRATOR,
)
from core.models import User

logger = logging.getLogger(__name__)


def approve_orgs(app, schema):
    user = (
        User.objects.filter(groups__name__in=[SECURITY_GROUP_TRA_ADMINISTRATOR])
        .order_by("created_at")
        .first()
    )
    caseroles = OrganisationCaseRole.objects.exclude(
        role__id__in=[ROLE_AWAITING_APPROVAL, ROLE_PREPARING, ROLE_REJECTED]
    ).update(approved_at=timezone.now(), approved_by=user)
    logger.info(caseroles)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("security", "0005_auto_20190901_2005"),
    ]

    operations = [
        migrations.AddField(
            model_name="organisationcaserole",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="organisationcaserole",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="approved_by",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(approve_orgs),
    ]
