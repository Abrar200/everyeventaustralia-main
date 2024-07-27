# Generated by Django 4.2.13 on 2024-07-21 00:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0026_remove_productvariation_image_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceVariation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.RemoveField(
            model_name='service',
            name='price',
        ),
        migrations.AddField(
            model_name='service',
            name='available_by_quotation_only',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='service',
            name='has_variations',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='service',
            name='hire_duration',
            field=models.CharField(blank=True, choices=[('hours', 'Hours'), ('days', 'Days'), ('weeks', 'Weeks')], max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='service',
            name='hire_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='service',
            name='setup_packdown_fee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='service',
            name='setup_packdown_fee_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.CreateModel(
            name='ServiceVariationOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=100)),
                ('price_varies', models.BooleanField(default=False)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('variation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='event.servicevariation')),
            ],
        ),
        migrations.AddField(
            model_name='servicevariation',
            name='service',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variations', to='event.service'),
        ),
    ]
