# Generated by Django 3.0.5 on 2020-05-21 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_auto_20200520_2046'),
    ]

    operations = [
        migrations.AddField(
            model_name='publication',
            name='is_paywalled',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name='author',
            name='is_collaboration',
            field=models.BooleanField(db_index=True),
        ),
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='share',
            name='status',
            field=models.IntegerField(choices=[(4, 'Credibility Finalized'), (3, 'Credibility Allocated'), (2, 'Sentiment Calculated'), (1, 'Article Associated'), (0, 'Created'), (-1, 'Fetch Error'), (-2, 'Article Error'), (-3, 'Sentiment Error'), (-4, 'Self Share'), (-5, 'Duplicate Share')], db_index=True),
        ),
    ]