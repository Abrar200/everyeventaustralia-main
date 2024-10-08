# Generated by Django 4.2.13 on 2024-07-26 01:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('event', '0036_venue_states'),
    ]

    operations = [
        migrations.AddField(
            model_name='venue',
            name='views_count',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='VenueView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(auto_now_add=True)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='views', to='event.venue')),
            ],
        ),
        migrations.CreateModel(
            name='VenueInquiry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('event_date', models.DateField()),
                ('guests', models.PositiveIntegerField()),
                ('comments', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inquiries', to='event.venue')),
            ],
        ),
    ]
