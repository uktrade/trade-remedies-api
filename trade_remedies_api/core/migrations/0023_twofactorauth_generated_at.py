# Generated by Django 2.2.6 on 2020-04-15 08:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_userprofile_email_verify_code_last_sent"),
    ]

    operations = [
        migrations.AddField(
            model_name="twofactorauth",
            name="generated_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
