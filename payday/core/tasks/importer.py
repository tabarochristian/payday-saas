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
    # Read Excel and normalize missing values
    df = pd.read_excel(obj.document, sheet_name=0, dtype=str)
    df.replace({np.nan: None, '': None}, inplace=True)
    df = df.where(pd.notnull(df), None)

    # Normalize column names based on field mappings
    df.columns = [
        fields[col.lower()].name if col.lower() in fields else col
        for col in df.columns
    ]

    # Identify related fields and fetch their ID mappings
    related_fields = {
        field.name: field.related_model.objects.values('id', 'name') 
        for field in fields.values()
        if field.is_relation and field.name in df.columns
    }

    pks = {
        field.name: field.remote_field.model._meta.pk.name
        for field in fields.values()
        if field.is_relation and field.name in df.columns
    }

    # Add system fields
    df['created_by_id'] = obj.created_by.id
    df['updated_by_id'] = obj.created_by.id

    # Convert related fields to foreign key IDs
    rename_map = {}
    for field_name, choices in related_fields.items():
        pk_field = pks[field_name]
        mapping = {choice['name']: choice['id'] for choice in choices}
        df[field_name] = df[field_name].map(mapping).replace({np.nan: None})
        rename_map[field_name] = f"{field_name}_{pk_field}"

    df.rename(columns=rename_map, inplace=True)

    # Parse date fields
    for field in fields.values():
        if (
            'date' in field.get_internal_type().lower()
            and field.name in df.columns
        ):
            df[field.name] = pd.to_datetime(df[field.name], errors='coerce').where(
                df[field.name].notnull(), None
            )

    # Metadata extraction
    metadata_cols = [
        col for col in df.columns
        if col.lower().startswith("metadata.")
    ]

    if metadata_cols:
        def extract_metadata(row):
            return {
                col.split('.', 1)[1]: row[col]
                for col in metadata_cols
                if row.get(col) is not None and '.' in col
            }

        df["_metadata"] = df[metadata_cols].apply(extract_metadata, axis=1)
        df.drop(columns=metadata_cols, inplace=True)

    # Final cleanup
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