# Generated by Django 2.2.5 on 2020-02-12 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_systemparameter_editable"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="last_modified",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
