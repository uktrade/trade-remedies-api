# Generated by Django 3.2.14 on 2022-08-18 16:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invitations', '0013_auto_20220815_1512'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='invitation_type',
            field=models.PositiveIntegerField(blank=True, choices=[(1, 'Own Organisation'), (2, 'Representative')], null=True),
        ),
    ]
