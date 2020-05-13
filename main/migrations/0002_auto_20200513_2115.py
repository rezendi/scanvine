# Generated by Django 3.0.5 on 2020-05-13 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='total_credibility',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='article',
            name='url',
            field=models.URLField(blank=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='author',
            name='twitter_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='share',
            name='net_sentiment',
            field=models.DecimalField(blank=True, db_index=True, decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AlterField(
            model_name='share',
            name='status',
            field=models.IntegerField(choices=[(4, 'Credibility Finalized'), (3, 'Credibility Allocated'), (2, 'Sentiment Calculated'), (1, 'Article Associated'), (0, 'Created'), (-1, 'Fetch Error'), (-2, 'Article Error'), (-3, 'Sentiment Error')], db_index=True),
        ),
        migrations.AlterField(
            model_name='sharer',
            name='category',
            field=models.IntegerField(choices=[(0, 'Health'), (1, 'Science'), (2, 'Tech'), (3, 'Business'), (4, 'Media')], db_index=True),
        ),
        migrations.AlterField(
            model_name='sharer',
            name='status',
            field=models.IntegerField(choices=[(2, 'Listed'), (1, 'Selected'), (0, 'Created'), (-1, 'Deselected'), (-2, 'Disabled')], db_index=True),
        ),
        migrations.AlterField(
            model_name='sharer',
            name='twitter_list_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
