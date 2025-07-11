# Generated by Django 5.1.3 on 2025-06-29 06:32

import core.models.base
import core.models.fields.choice_field
import core.models.fields.datetimefield
import core.models.fields.floatfield
import core.models.fields.integerfield
import core.models.fields.jsonfield
import core.models.fields.model_select_field
import django.db.models.deletion
import django_currentuser.db.models.fields
import django_currentuser.middleware
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("payroll", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Mobile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "_metadata",
                    core.models.fields.jsonfield.JSONField(
                        blank=True, default=dict, verbose_name="metadata"
                    ),
                ),
                (
                    "sub_organization",
                    core.models.fields.choice_field.ChoiceField(
                        blank=True,
                        choices=core.models.base.get_category_choices,
                        max_length=100,
                        null=True,
                        verbose_name="sous-organization",
                    ),
                ),
                (
                    "updated_at",
                    core.models.fields.datetimefield.DateTimeField(
                        auto_now=True, verbose_name="mis à jour le/à"
                    ),
                ),
                (
                    "created_at",
                    core.models.fields.datetimefield.DateTimeField(
                        auto_now_add=True, verbose_name="créé le/à"
                    ),
                ),
                (
                    "count",
                    core.models.fields.integerfield.IntegerField(
                        default=0, verbose_name="Nombre de personnes à payer"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "En attente"),
                            ("PROCESSING", "En cours"),
                            ("COMPLETED", "Complété"),
                            ("ERROR", "Erreur"),
                            ("CANCELLED", "Annulé"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "executed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Date d'exécution"
                    ),
                ),
                (
                    "amount_total",
                    core.models.fields.floatfield.FloatField(
                        default=0, verbose_name="Montant total"
                    ),
                ),
                (
                    "amount_paid",
                    core.models.fields.floatfield.FloatField(
                        default=0, verbose_name="Montant payé"
                    ),
                ),
                (
                    "created_by",
                    django_currentuser.db.models.fields.CurrentUserField(
                        default=django_currentuser.middleware.get_current_authenticated_user,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "payroll",
                    core.models.fields.model_select_field.ModelSelectField(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="payroll.payroll",
                        verbose_name="Paie",
                    ),
                ),
                (
                    "updated_by",
                    django_currentuser.db.models.fields.CurrentUserField(
                        default=django_currentuser.middleware.get_current_authenticated_user,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        on_update=True,
                        related_name="%(app_label)s_%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "mobile money",
                "verbose_name_plural": "mobile moneys",
            },
        ),
    ]
