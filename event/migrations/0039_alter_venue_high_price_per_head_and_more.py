# Generated by Django 4.2.13 on 2024-07-27 05:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0038_business_price_per_way'),
    ]

    operations = [
        migrations.AlterField(
            model_name='venue',
            name='high_price_per_head',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='venue',
            name='low_price_per_head',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='venue',
            name='price_per_event',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
