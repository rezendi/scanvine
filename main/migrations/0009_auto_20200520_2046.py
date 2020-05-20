# Generated by Django 3.0.5 on 2020-05-20 20:46

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import main.models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_auto_20200520_0024'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='average_credibility',
            field=models.BigIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name='author',
            name='is_collective',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name='article',
            name='status',
            field=models.IntegerField(choices=[(3, 'Author Associated'), (2, 'Publisher Associated'), (1, 'Metadata Parsed'), (0, 'Created'), (-1, 'Publication Parse Error'), (-2, 'Metadata Parse Error'), (-3, 'Author Not Found'), (-4, 'Potential Duplicate')], db_index=True),
        ),
        migrations.AlterField(
            model_name='author',
            name='total_credibility',
            field=models.BigIntegerField(db_index=True, default=0),
        ),
        migrations.AlterField(
            model_name='publication',
            name='scores',
            field=django.contrib.postgres.fields.jsonb.JSONField(db_index=True, default=main.models.default_publication_scores),
        ),
    ]