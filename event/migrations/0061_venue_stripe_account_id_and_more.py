# Generated by Django 4.2.13 on 2024-08-14 12:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0060_order_payment_intent'),
    ]

    operations = [
        migrations.AddField(
            model_name='venue',
            name='stripe_account_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='venue',
            name='subscription_start_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
