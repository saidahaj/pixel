# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-10 16:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_analysis_notebook_url'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='experiment',
            name='primary_data_url',
        ),
    ]
