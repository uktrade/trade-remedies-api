# Generated by Django 2.2.4 on 2019-09-03 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0038_auto_20190804_2250"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submissiondocument",
            name="issued",
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
