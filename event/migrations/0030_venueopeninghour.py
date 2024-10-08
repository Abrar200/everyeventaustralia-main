# Generated by Django 4.2.13 on 2024-07-22 11:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0029_venue_venueimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='VenueOpeningHour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.CharField(choices=[('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'), ('sunday', 'Sunday'), ('public_holiday', 'Public Holiday')], max_length=20)),
                ('is_closed', models.BooleanField(default=False)),
                ('opening_time', models.TimeField(blank=True, null=True)),
                ('closing_time', models.TimeField(blank=True, null=True)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='venu_opening_hours', to='event.venue')),
            ],
        ),
    ]
