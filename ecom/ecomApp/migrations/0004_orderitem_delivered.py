# Generated by Django 5.2.4 on 2025-07-26 11:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecomApp', '0003_feedback_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='delivered',
            field=models.BooleanField(default=False),
        ),
    ]
