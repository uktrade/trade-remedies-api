# Generated by Django 3.2.15 on 2022-10-19 11:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0013_alter_organisation_json_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organisation",
            name="name",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
