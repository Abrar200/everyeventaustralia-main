# Generated by Django 4.2.13 on 2024-07-30 12:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0046_cart_quick_hire'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cart',
            old_name='quick_hire',
            new_name='hire',
        ),
    ]
