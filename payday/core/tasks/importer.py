from django.utils.translation import gettext as _
from core.models import ImporterStatus, Importer
from django.template import loader
from notifications import signals
from core.utils import set_schema
from celery import shared_task
import pandas as pd
import numpy as np

@shared_task(name='importer')
def importer(pk, schema=None):
    if schema:
        set_schema(schema)
    obj = Importer.objects.get(pk=pk)

    if not user_has_permission(obj):
        handle_permission_error(obj)
        return

    # Update status to processing
    update_status(obj, ImporterStatus.PROCESSING)

    model = obj.content_type.model_class()
    fields = get_model_fields(model)

    data = process_excel_file(obj, fields)
    bulk_create_records(model, data)
    notify(obj, _('Importation réussie'), _('Les données ont été importées avec succès'))
    update_status(obj, ImporterStatus.SUCCESS)

    """
    try:
        data = process_excel_file(obj, fields)
        bulk_create_records(model, data)
        notify(obj, _('Importation réussie'), _('Les données ont été importées avec succès'))
        update_status(obj, ImporterStatus.SUCCESS)
    except Exception as e:
        handle_import_error(obj, str(e))
    """

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
    df = pd.read_excel(obj.document, sheet_name=0, dtype=str)
    df = df.replace({np.nan: None, '': None})
    df = df.where(pd.notnull(df), None)

    df.columns = [fields[col.lower()].name for col in df.columns]
    related_fields = {field.name: field.related_model.objects.values('id', 'name') 
        for field in fields.values() if field.is_relation and field.name in df.columns}

    # Add constant values to all rows
    df['created_by_id'] = obj.created_by.id
    df['updated_by_id'] = obj.created_by.id
    

    # Convert related fields to foreign key ids using mapping
    pks = {field.name: field.remote_field.model._meta.pk.name
        for field in fields.values() if field.is_relation and field.name in df.columns}

    columns = {}
    for field, choices in related_fields.items():
        pk_field = pks[field]
        choices_dict = {choice['name']: choice['id'] for choice in choices}
        df[field] = df[field].map(choices_dict)
        df[field] = df[field].replace({np.nan: None})
        columns[field] = f'{field}_{pk_field}'
    
    for name, field in fields.items():
        if 'date' not in field.get_internal_type().lower() or field.name not in df.columns:
            continue
        df[field.name] = df[field.name].where(df[field.name].isnull(), pd.to_datetime(df[field.name], errors='coerce'))

    # rename field
    df.rename(columns=columns, inplace=True)

    # replace all nan by None
    df = df.where(pd.notnull(df), None)
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