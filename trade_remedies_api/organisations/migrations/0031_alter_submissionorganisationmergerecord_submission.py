# Generated by Django 3.2.15 on 2023-06-07 14:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0067_auto_20230605_1447'),
        ('organisations', '0030_rename_new_id_submissionorganisationmergerecord_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissionorganisationmergerecord',
            name='submission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cases.submission'),
        ),
    ]