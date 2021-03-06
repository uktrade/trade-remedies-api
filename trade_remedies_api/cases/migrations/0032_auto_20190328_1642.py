# Generated by Django 2.0.13 on 2019-03-28 16:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0031_auto_20190322_1010"),
    ]

    operations = [
        migrations.AddField(
            model_name="casedocument",
            name="case_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="cases.CaseType",
            ),
        ),
        migrations.AlterField(
            model_name="casedocument",
            name="case",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="cases.Case"
            ),
        ),
    ]
