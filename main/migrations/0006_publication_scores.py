# Generated by Django 3.0.5 on 2020-05-19 20:17

import django.contrib.postgres.fields.jsonb
from django.db import migrations
import main.models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_auto_20200517_0457'),
    ]

    operations = [
        migrations.AddField(
            model_name='publication',
            name='scores',
            field=django.contrib.postgres.fields.jsonb.JSONField(db_index=True, default=main.models.default_scores),
        ),
    ]