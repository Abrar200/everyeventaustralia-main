# Generated by Django 4.2.13 on 2024-07-16 12:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0019_business_latitude_business_longitude_order_latitude_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='address',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
