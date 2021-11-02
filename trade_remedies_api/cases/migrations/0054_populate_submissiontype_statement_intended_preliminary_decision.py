import logging

from django.db import migrations, IntegrityError

import cases.constants as constants

logger = logging.getLogger(__name__)


PUBLIC_KEY = "public"
AD_HOC_KEY = "adhoc"
QUESTIONNAIRE_KEY = "questionnaire"


submission_type_values = {
    constants.SUBMISSION_TYPE_STATEMENT_OF_INTENDED_PRELIMINARY_DECISION: {
        "name": "Statement of intended preliminary decision",
        "key": PUBLIC_KEY,
        "direction": 0,
        "order": 30,
    },
}


def create_submission_type_statement_of_intended_preliminary_decision(apps, schema_editor):  # noqa
    """Create or update submission types.

    Formerly submission type initial data was loaded using json fixtures.
    This migration takes a preferred approach to load those data using
    `submission_type_values` defined in this module.
    """
    submission_type_class = apps.get_model("cases", "SubmissionType")
    for key, values in submission_type_values.items():
        try:
            submission_type_class.objects.update_or_create(id=key, defaults=values)
        except IntegrityError as e:
            logger.critical(f"Migration error! You may need to manually address this issue: {e}")


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0053_populate_submissionstatus"),
    ]

    operations = [
        migrations.RunPython(create_submission_type_statement_of_intended_preliminary_decision),
    ]
