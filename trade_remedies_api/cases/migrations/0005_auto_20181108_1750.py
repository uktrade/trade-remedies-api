# Generated by Django 2.0.1 on 2018-11-08 17:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0004_auto_20181101_1647"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubmissionDocumentType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=250)),
                ("key", models.CharField(max_length=20)),
            ],
        ),
        migrations.AddField(
            model_name="submissiondocument",
            name="type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="cases.SubmissionDocumentType",
            ),
        ),
    ]
