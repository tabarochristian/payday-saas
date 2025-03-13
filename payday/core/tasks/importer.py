from django.utils.translation import gettext as _
from core.models import ImporterStatus, Importer
from django.urls import reverse_lazy
from django.template import loader
from notifications import signals
from celery import shared_task
import pandas as pd


@shared_task(name='importer')
def importer(pk):
    obj = Importer.objects.get(pk=pk)

    if not user_has_permission(obj):
        handle_permission_error(obj)
        return

    # Update status to processing
    update_status(obj, ImporterStatus.PROCESSING)

    model = obj.content_type.model_class()
    fields = get_model_fields(model)

    try:
        data = process_excel_file(obj, fields)
        bulk_create_records(model, data)
        notify(obj, _('Importation réussie'), _('Les données ont été importées avec succès'))
        update_status(obj, ImporterStatus.SUCCESS)
    except Exception as e:
        handle_import_error(obj, str(e))

def user_has_permission(obj):
    permission = f'{obj.content_type.app_label}.add_{obj.content_type.model}'
    return obj.created_by.has_perm(permission)

def handle_permission_error(obj):
    obj.message = _('Vous n\'avez pas la permission d\'ajouter des données')
    obj.status = ImporterStatus.ERROR
    obj.save()
    try:
        obj.created_by.email_user(
            subject=_(f'Importation a échoué'),
            message=loader.render_to_string('email/importation_failed.txt')
        )
    except Exception as e:
        print(f'Email not sent: {e}')

def update_status(obj, status):
    obj.status = status
    obj.save()

def get_model_fields(model):
    return {field.verbose_name.lower(): field for field in model._meta.fields}

def process_excel_file(obj, fields):
    df = pd.read_excel(obj.document)
    df = df.where(pd.notnull(df), None)
    df.columns = [fields[col.lower()].name for col in df.columns]
    related_fields = {field.name: field.related_model.objects.values('id', 'name') for field in fields.values() if field.is_relation and field.name in df.columns}

    # Add constant values to all rows
    df['organization_id'] = obj.created_by.organization.id
    df['created_by_id'] = obj.created_by.id

    # Convert related fields to foreign key ids using mapping
    for field, choices in related_fields.items():
        choices_dict = {choice['name']: choice['id'] for choice in choices}
        df[f'{field}_id'] = df[field].map(choices_dict)

    # Drop the original related fields
    df.drop(columns=related_fields.keys(), inplace=True)
    return df.to_dict(orient='records')

def bulk_create_records(model, data):
    records = [model(**row) for row in data]
    model.objects.bulk_create(records, ignore_conflicts=True)

def notify(obj, subject, message, level='info'):
    signals.notify.send(
        obj.created_by,
        recipient=obj.created_by,
        verb=subject,
        level=level,
        action_object=obj,
        target=obj,
        description=message,
        public=False,
    )

def handle_import_error(obj, error_message):
    notify(obj, _('Importation échouée'), error_message)
    obj.status = ImporterStatus.ERROR
    obj.message = error_message
    obj.save()