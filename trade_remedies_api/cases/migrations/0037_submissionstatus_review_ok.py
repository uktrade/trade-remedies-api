# Generated by Django 2.0.13 on 2019-05-07 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0036_auto_20190502_1532"),
    ]

    operations = [
        migrations.AddField(
            model_name="submissionstatus",
            name="review_ok",
            field=models.BooleanField(default=False),
        ),
    ]
