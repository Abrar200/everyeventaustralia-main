# Generated by Django 4.2.13 on 2024-07-16 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0017_product_delivery_radius_product_main_colour_theme_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='image3',
            field=models.ImageField(blank=True, null=True, upload_to='products/'),
        ),
        migrations.AddField(
            model_name='product',
            name='image4',
            field=models.ImageField(blank=True, null=True, upload_to='products/'),
        ),
    ]
