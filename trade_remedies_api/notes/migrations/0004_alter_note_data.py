# Generated by Django 3.2.12 on 2022-02-07 12:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0003_note_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='note',
            name='data',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
