# Generated by Django 5.0.6 on 2024-10-17 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FeedResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voting_round_id', models.PositiveBigIntegerField()),
                ('feed_id', models.CharField(max_length=42)),
                ('value', models.BigIntegerField()),
                ('turnout_bips', models.PositiveBigIntegerField()),
                ('decimals', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='RandomResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voting_round_id', models.PositiveBigIntegerField()),
                ('value', models.CharField(max_length=64)),
                ('is_secure', models.BooleanField()),
            ],
        ),
    ]
