# Generated by Django 5.1.3 on 2025-02-02 08:51

import core.models.fields.model_select_field
import django.db.models.deletion
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("employee", "0002_employee_create_user_on_save_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendance",
            name="employee",
            field=core.models.fields.model_select_field.ModelSelectField(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="employee.employee",
                verbose_name="employé",
            ),
        ),
        migrations.AlterField(
            model_name="device",
            name="branch",
            field=core.models.fields.model_select_field.ModelSelectField(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="employee.branch",
                verbose_name="site",
            ),
        ),
    ]
