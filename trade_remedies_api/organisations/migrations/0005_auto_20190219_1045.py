# Generated by Django 2.0.1 on 2019-02-19 10:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0004_organisation_tra_organisation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organisation",
            name="duplicate_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="organisations.Organisation",
            ),
        ),
    ]
