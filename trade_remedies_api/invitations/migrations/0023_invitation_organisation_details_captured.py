# Generated by Django 3.2.16 on 2023-02-14 16:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invitations', '0022_invitation_authorised_signatory'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='organisation_details_captured',
            field=models.BooleanField(null=True),
        ),
    ]
