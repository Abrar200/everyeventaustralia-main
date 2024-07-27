# Generated by Django 4.2.13 on 2024-07-27 03:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0037_venue_views_count_venueview_venueinquiry'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='price_per_way',
            field=models.IntegerField(blank=True, help_text='Enter the delivery fee per way. The total fee will be twice this amount for a round trip.', null=True),
        ),
    ]
