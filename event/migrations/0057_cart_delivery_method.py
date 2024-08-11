# Generated by Django 4.2.13 on 2024-08-06 01:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0056_remove_order_delivery_method_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='delivery_method',
            field=models.CharField(choices=[('pickup', 'Pickup'), ('delivery', 'Delivery')], default='delivery', max_length=10),
        ),
    ]
