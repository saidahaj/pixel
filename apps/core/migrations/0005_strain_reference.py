# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-16 08:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
        ('core', '0004_auto_20171016_0826'),
    ]

    operations = [
        migrations.AddField(
            model_name='strain',
            name='reference',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='strains', related_query_name='strain', to='data.Entry'),
        ),
    ]
