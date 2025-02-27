# Generated by Django 5.0.6 on 2024-10-17 16:17

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AttestationResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voting_round_id', models.PositiveBigIntegerField()),
                ('request_hex', models.CharField()),
                ('response_hex', models.CharField()),
                ('abi', models.CharField()),
                ('proof', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(), size=None)),
            ],
        ),
    ]
