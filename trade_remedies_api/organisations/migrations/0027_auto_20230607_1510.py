# Generated by Django 3.2.15 on 2023-06-07 14:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organisations', '0026_auto_20230607_1504'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionorganisationmergerecord',
            name='id',
            field=models.AutoField(auto_created=True, default=None, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='submissionorganisationmergerecord',
            name='new_id',
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
    ]
