# Generated by Django 3.0.5 on 2020-05-16 03:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_auto_20200515_2243'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='article',
            name='first_published_at',
        ),
        migrations.RemoveField(
            model_name='sharer',
            name='metadata_change_date',
        ),
        migrations.RemoveField(
            model_name='sharer',
            name='previous_metadata',
        ),
    ]