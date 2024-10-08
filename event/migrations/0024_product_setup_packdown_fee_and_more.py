# Generated by Django 4.2.13 on 2024-07-20 07:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0023_business_delivery_radius_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='setup_packdown_fee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='product',
            name='setup_packdown_fee_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
