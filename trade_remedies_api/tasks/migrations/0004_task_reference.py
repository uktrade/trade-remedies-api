# Generated by Django 2.2.6 on 2020-02-25 12:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0003_auto_20200204_1246"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="reference",
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
