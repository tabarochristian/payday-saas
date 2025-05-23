# Generated by Django 5.1.3 on 2025-05-17 11:17

import core.models.fields.foreignkey
import django.db.models.deletion
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0010_alter_fieldpermission_field_content_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fieldpermission",
            name="field_content_type",
            field=core.models.fields.foreignkey.ForeignKey(
                default=None,
                help_text="Le modèle auquel cette règle de filtrage est associée.",
                limit_choices_to={"app_label__in": ["core", "employee", "payroll"]},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="contenttypes.contenttype",
                verbose_name="type de contenu",
            ),
        ),
        migrations.AlterField(
            model_name="rowlevelsecurity",
            name="row_content_type",
            field=core.models.fields.foreignkey.ForeignKey(
                default=None,
                help_text="Le modèle auquel cette règle de filtrage est associée.",
                limit_choices_to={"app_label__in": ["core", "employee", "payroll"]},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="contenttypes.contenttype",
                verbose_name="type de contenu",
            ),
        ),
    ]
