# Generated by Django 3.2.14 on 2022-09-14 15:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0006_auto_20190617_0850'),
        ('cases', '0059_auto_20220812_1553'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='primary_contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='submission_primary_contacts', to='contacts.contact'),
        ),
    ]
