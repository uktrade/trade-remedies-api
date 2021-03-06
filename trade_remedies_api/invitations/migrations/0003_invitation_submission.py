# Generated by Django 2.0.1 on 2018-11-06 10:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0004_auto_20181101_1647"),
        ("invitations", "0002_auto_20181015_1444"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="submission",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="cases.Submission",
            ),
        ),
    ]
