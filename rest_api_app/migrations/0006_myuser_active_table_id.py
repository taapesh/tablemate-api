# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-01 07:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rest_api_app', '0005_auto_20160131_1956'),
    ]

    operations = [
        migrations.AddField(
            model_name='myuser',
            name='active_table_id',
            field=models.IntegerField(default=-1),
        ),
    ]
