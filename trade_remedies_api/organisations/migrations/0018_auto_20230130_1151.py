# Generated by Django 3.2.15 on 2023-01-30 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0017_auto_20230123_1424"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="organisationmergerecord",
            name="submission",
        ),
        migrations.AlterField(
            model_name="duplicateorganisationmerge",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed_not_duplicate", "Not duplicate"),
                    ("confirmed_duplicate", "Confirmed duplicate"),
                    ("attributes_selected", "Attributes selected"),
                ],
                default="pending",
                max_length=30,
            ),
        ),
        migrations.DeleteModel(
            name="SubmissionOrganisationMergeRecord",
        ),
    ]
