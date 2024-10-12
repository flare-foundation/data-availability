# Generated by Django 5.0.6 on 2024-10-12 16:52

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ProtocolMessageRelayed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('protocol_id', models.PositiveSmallIntegerField()),
                ('voting_round_id', models.PositiveIntegerField()),
                ('is_secure_random', models.BooleanField()),
                ('merkle_root', models.CharField(max_length=64)),
            ],
            options={
                'unique_together': {('protocol_id', 'voting_round_id')},
            },
        ),
    ]
