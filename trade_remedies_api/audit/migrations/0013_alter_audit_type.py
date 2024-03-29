# Generated by Django 3.2.13 on 2022-06-06 13:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0012_alter_audit_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="audit",
            name="type",
            field=models.CharField(
                choices=[
                    ("UPDATE", "Update"),
                    ("CREATE", "Create"),
                    ("DELETE", "Delete"),
                    ("PURGE", "Purge"),
                    ("RESTORE", "Restore"),
                    ("READ", "Read"),
                    ("LOGIN", "Log In"),
                    ("LOGIN_FAILED", "Log In Failed"),  # /PS-IGNORE
                    ("LOGOUT", "Log Out"),  # /PS-IGNORE
                    ("EVENT", "Event"),
                    ("ATTACH", "Attach"),
                    ("NOTIFY", "Notify"),
                    ("DELIVERED", "Delivery"),
                    ("PASSWORD_RESET", "Password Reset"),  # /PS-IGNORE
                    ("PASSWORD_RESET_FAILED", "Password Reset Failed"),  # /PS-IGNORE
                ],
                max_length=50,
            ),
        ),
    ]
