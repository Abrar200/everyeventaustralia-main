# Generated by Django 4.2.13 on 2024-08-05 02:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0053_order_delivery_method_order_event_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(choices=[('card', 'Credit Card'), ('afterpay_clearpay', 'Afterpay')], default='card', max_length=20),
        ),
    ]
