# Generated by Django 3.0.5 on 2020-05-03 01:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(db_index=True, max_length=5)),
                ('status', models.IntegerField(choices=[(3, 'Author Associated'), (2, 'Publisher Associated'), (1, 'Metadata Parsed'), (0, 'Created'), (-1, 'Publication Parse Error'), (-2, 'Metadata Parse Error'), (-3, 'Author Not Found')], db_index=True)),
                ('url', models.URLField(db_index=True)),
                ('initial_url', models.URLField(blank=True, null=True)),
                ('title', models.CharField(blank=True, max_length=255)),
                ('contents', models.TextField()),
                ('metadata', models.TextField(blank=True, default='')),
                ('published_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('first_published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.IntegerField(choices=[(0, 'Created')], db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('is_collaboration', models.BooleanField()),
                ('twitter_id', models.BigIntegerField(db_index=True, null=True)),
                ('twitter_screen_name', models.CharField(blank=True, default='', max_length=63)),
                ('metadata', models.TextField(blank=True, default='')),
                ('current_credibility', models.BigIntegerField()),
                ('total_credibility', models.BigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.IntegerField(choices=[(1, 'Completed'), (0, 'Launched'), (-1, 'Error')], db_index=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('actions', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Publication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.IntegerField(db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('url_policy', models.CharField(blank=True, default='', max_length=255)),
                ('parser_rules', models.TextField(blank=True, default='')),
                ('average_credibility', models.BigIntegerField()),
                ('total_credibility', models.BigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Sharer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.IntegerField(choices=[(1, 'Listed'), (0, 'Created'), (-1, 'Disabled')], db_index=True)),
                ('category', models.IntegerField()),
                ('twitter_list_id', models.BigIntegerField(null=True)),
                ('twitter_id', models.BigIntegerField(db_index=True, null=True)),
                ('twitter_screen_name', models.CharField(blank=True, default='', max_length=63)),
                ('verified', models.BooleanField()),
                ('name', models.CharField(max_length=255)),
                ('profile', models.CharField(max_length=1023)),
                ('metadata_change_date', models.DateTimeField(blank=True, null=True)),
                ('previous_metadata', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Tranche',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.IntegerField()),
                ('status', models.IntegerField()),
                ('sender', models.BigIntegerField(db_index=True)),
                ('receiver', models.BigIntegerField(db_index=True)),
                ('quantity', models.IntegerField()),
                ('category', models.IntegerField()),
                ('type', models.IntegerField()),
                ('tags', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Share',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.IntegerField(choices=[(4, 'Aggregates Updated'), (3, 'Credibility Allocated'), (2, 'Sentiment Calculated'), (1, 'Article Associated'), (0, 'Created'), (-1, 'Fetch Error'), (-2, 'Article Error')], db_index=True)),
                ('twitter_id', models.BigIntegerField(db_index=True, null=True)),
                ('source', models.IntegerField(db_index=True, default=0)),
                ('language', models.CharField(db_index=True, max_length=5)),
                ('text', models.CharField(max_length=4095)),
                ('url', models.URLField()),
                ('sentiment', models.CharField(blank=True, max_length=1023)),
                ('net_sentiment', models.DecimalField(db_index=True, decimal_places=2, max_digits=4, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.Article')),
                ('sharer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='main.Sharer')),
            ],
        ),
        migrations.CreateModel(
            name='Collaboration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('individual', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaborations', to='main.Author')),
                ('partnership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaborators', to='main.Author')),
            ],
        ),
        migrations.AddField(
            model_name='article',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.Author'),
        ),
        migrations.AddField(
            model_name='article',
            name='publication',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.Publication'),
        ),
    ]