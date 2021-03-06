# Generated by Django 2.0.13 on 2019-04-09 08:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0032_auto_20190328_1642"),
        ("documents", "0002_documentbundle"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentbundle",
            name="case",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="cases.Case"
            ),
        ),
        migrations.AddField(
            model_name="documentbundle",
            name="submission_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="cases.SubmissionType",
            ),
        ),
    ]
