# Generated by Django 3.2.15 on 2023-06-07 14:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organisations', '0029_auto_20230607_1515'),
    ]

    operations = [
        migrations.RenameField(
            model_name='submissionorganisationmergerecord',
            old_name='new_id',
            new_name='id',
        ),
    ]
