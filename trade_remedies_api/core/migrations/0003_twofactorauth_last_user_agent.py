# Generated by Django 2.0.1 on 2018-12-26 00:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_auto_20181218_1929"),
    ]

    operations = [
        migrations.AddField(
            model_name="twofactorauth",
            name="last_user_agent",
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
