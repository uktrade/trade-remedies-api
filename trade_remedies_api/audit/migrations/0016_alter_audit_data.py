# Generated by Django 3.2.14 on 2022-08-18 16:03

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0015_alter_audit_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audit',
            name='data',
            field=models.JSONField(blank=True, encoder=django.core.serializers.json.DjangoJSONEncoder, null=True),
        ),
    ]
