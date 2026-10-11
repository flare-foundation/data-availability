from django.db import migrations, models


class Migration(migrations.Migration):
    # A proposal's trigger reference names the account as
    # 0x<sourceId>/<senderAddress>, which for a P2WSH address passes 128.

    dependencies = [
        ("dal", "0002_expectation_params"),
    ]

    operations = [
        migrations.AlterField(
            model_name="expectation",
            name="trigger_ref",
            field=models.CharField(db_index=True, max_length=256),
        ),
    ]
