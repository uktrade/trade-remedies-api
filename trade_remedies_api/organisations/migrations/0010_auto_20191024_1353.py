# Generated by Django 2.2.5 on 2019-10-24 12:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0009_organisationname"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="organisation",
            options={"permissions": (("merge_organisations", "Can merge organisations"),)},
        ),
    ]
