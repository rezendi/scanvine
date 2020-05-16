# Generated by Django 3.0.5 on 2020-05-15 22:43

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import main.models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20200513_2115'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='scores',
            field=django.contrib.postgres.fields.jsonb.JSONField(db_index=True, default=main.models.default_scores),
        ),
        migrations.AlterField(
            model_name='article',
            name='total_credibility',
            field=models.BigIntegerField(db_index=True, default=0),
        ),
    ]
