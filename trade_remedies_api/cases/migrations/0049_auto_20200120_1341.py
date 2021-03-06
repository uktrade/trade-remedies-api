# Generated by Django 2.2.5 on 2020-01-20 13:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0048_auto_20200120_1225"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="notice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="cases.Notice",
            ),
        ),
        migrations.AlterField(
            model_name="notice",
            name="review_case",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="review_case",
                to="cases.Case",
            ),
        ),
    ]
