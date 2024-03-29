# Generated by Django 3.2.13 on 2022-08-09 12:44

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0013_alter_audit_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audit',
            name='data',
            field=models.JSONField(blank=True, encoder=django.core.serializers.json.DjangoJSONEncoder, null=True),
        ),
        migrations.AlterField(
            model_name='audit',
            name='type',
            field=models.CharField(choices=[('UPDATE', 'Update'), ('CREATE', 'Create'), ('DELETE', 'Delete'), ('PURGE', 'Purge'), ('RESTORE', 'Restore'), ('READ', 'Read'), ('LOGIN', 'Log In'), ('LOGIN_FAILED', 'Log In Failed'), ('LOGOUT', 'Log Out'), ('EVENT', 'Event'), ('ATTACH', 'Attach'), ('NOTIFY', 'Notify'), ('DELIVERED', 'Delivery'), ('PASSWORD_RESET', 'Password Reset'), ('PASSWORD_RESET_FAILED', 'Password Reset Failed'), ('USER_CREATED', 'New User Created'), ('EMAIL_VERIFIED', 'Email Verified')], max_length=50),
        ),
    ]
