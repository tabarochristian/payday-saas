from django.utils.translation import gettext as _
from core.models import ImporterStatus, Importer
from django.template import loader
from notifications import signals
from core.utils import set_schema
from celery import shared_task
from django.db.models import Field, ForeignKey
import pandas as pd
import numpy as np
from core.models import Base
from typing import Dict, Any, List, Optional, Type, Union
from django.db.models import Model
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import is_naive, make_aware, get_current_timezone
from core.signals import pre_bulk_save, post_bulk_save
from django.db import transaction


# --- Utility Functions ---

def update_importer_status(obj: Importer, status: ImporterStatus, message: Optional[str] = None) -> None:
    """Updates the Importer object's status and optionally sets a message."""
    obj.status = status
    if message:
        obj.message = message
    obj.save(update_fields=['status', 'message', 'updated_at'])

def notify_user(obj: Importer, subject: str, message: str, level: str = 'info') -> None:
    """Sends a notification signal to the user who initiated the import."""
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

def send_failure_email(obj: Importer) -> None:
    """Sends a failure email to the user."""
    try:
        obj.created_by.email_user(
            subject=_(f'Importation a échoué'),
            message=loader.render_to_string('email/importation_failed.txt')
        )
    except Exception as e:
        # Log this error instead of just printing
        print(f'Email not sent for Importer {obj.pk}: {e}')

def handle_importer_error(obj: Importer, error_message: str) -> None:
    """Handles an import error by notifying the user and updating the Importer object."""
    notify_user(obj, _('Importation échouée'), error_message, level='error')
    update_importer_status(obj, ImporterStatus.ERROR, error_message)
    # Optionally send a failure email here if desired
    # send_failure_email(obj)

def get_model_field_map(model: Type[Model]) -> Dict[str, Field]:
    """Returns a map of {verbose_name.lower(): field_object} for all model fields."""
    # Use _meta.fields which only includes concrete fields (columns in the DB table)
    return {field.verbose_name.lower(): field for field in model._meta.fields}

def get_relation_key_field(field: ForeignKey) -> Optional[str]:
    """Determines the likely natural key field for a related model."""
    # Prioritize fields that are commonly used as natural keys
    search_fields = ["name", "registration_number", "code", "slug"] 
    # Use related_model._meta.get_fields() to get all fields, not just concrete ones
    field_names = [f.name for f in field.remote_field.model._meta.get_fields()] 
    
    return next((item for item in search_fields if item in field_names), None)

def get_field_names_by_internal_type(model: Type[Model], types: Union[str, List[str]]) -> List[str]:
    """
    FIX: Renamed function and changed return type to return FIELD NAMES (not verbose names).
    Returns the names of concrete fields whose internal type matches one of the given types.
    """
    if isinstance(types, str):
        types = [types]

    # Exclude Base model fields to avoid internal system columns
    base_field_names = {field.name for field in Base._meta.fields}
 
    # Use _meta.fields for concrete fields
    return [
        f.name  # FIX: Return f.name (actual field name)
        for f in model._meta.fields
        if f.get_internal_type() in types and f.name not in base_field_names
    ]

def normalize_column_names(df: pd.DataFrame, field_map: Dict[str, Field]) -> pd.DataFrame:
    """Renames DataFrame columns using the model field verbose names to field names map."""
    rename_map = {}
    for col in df.columns:
        # Lowercase the column name for case-insensitive matching with verbose names
        lower_col = str(col).lower().strip() 
        if lower_col in field_map:
            rename_map[col] = field_map[lower_col].name # Rename to the actual field name
        # If the column name is already a field name, it will be kept

    df.rename(columns=rename_map, inplace=True)
    return df

def map_related_fields_to_ids(df: pd.DataFrame, model: Type[Model], field_map: Dict[str, Field]) -> pd.DataFrame:
    """
    Identifies related fields, fetches their ID mappings efficiently, 
    and converts related field values in the DataFrame to Foreign Key IDs.
    """
    
    # 1. Identify relevant ForeignKey fields present in the DataFrame
    # Filter for fields that are ForeignKeys and whose actual field name is in the DataFrame
    # Note: df.columns now contains the actual model field names (after normalize_column_names)
    fk_fields: Dict[str, ForeignKey] = { 
        field.name: field 
        for field in field_map.values() 
        if isinstance(field, ForeignKey) and field.name in df.columns
    }
    
    # 2. Get all natural keys for all related models in one go
    for field_name, field in fk_fields.items():
        key_field = get_relation_key_field(field)
        
        if not key_field:
            print(f"Warning: No suitable natural key found for related model {field.remote_field.model.__name__} (Field: {field_name}). Skipping mapping for this column.")
            continue

        pk_name = field.remote_field.model._meta.pk.name
        
        # Optimized: Fetch only the key field and the primary key
        choices = field.remote_field.model.objects.values(key_field, pk_name) 

        # Create the mapping: {natural_key_value: pk_id}
        # FIX: Added .upper() to mapping key and .str.upper() to DF column for case-insensitive matching
        mapping = {
            # Normalize database key to uppercase for consistent mapping
            (choice[key_field].upper() if isinstance(choice[key_field], str) else choice[key_field]): choice[pk_name] 
            for choice in choices 
            if choice[key_field] is not None
        }
        
        # 3. Apply the mapping to the DataFrame column
        
        # Create a cleaned version of the column for mapping
        cleaned_col = df[field_name].apply(lambda x: x.strip().upper() if isinstance(x, str) else x)
        
        # Use a temporary column for mapping result
        temp_col = f"_{field_name}_mapped"
        
        # Map cleaned values to their ID, resulting in NaN for non-mapped values
        df[temp_col] = cleaned_col.map(mapping)
        
        # Drop the original column (which contained natural keys)
        df.drop(columns=[field_name], inplace=True)
        
        # Rename the new ID column to the expected FK field name (e.g., 'country' becomes 'country_id')
        fk_column_name = f"{field_name}_id" 
        df.rename(columns={temp_col: fk_column_name}, inplace=True)
    
    return df

def standardize_dates(df: pd.DataFrame, model: Type[Model], field_map: Dict[str, Field]) -> pd.DataFrame:
    """Ensures date/datetime fields are in the correct format and timezone-aware if needed."""

    # FIX: Use the fixed function which returns model field names
    date_fields = get_field_names_by_internal_type(model, ["DateField"])
    datetime_fields = get_field_names_by_internal_type(model, ["DateTimeField"])
    
    # Process DateFields
    for field_name in date_fields:
        if field_name in df.columns:
            # Convert to date, coercing errors to NaT
            df[field_name] = pd.to_datetime(df[field_name], errors='coerce').dt.date
            
    # Process DateTimeFields
    for field_name in datetime_fields:
        if field_name in df.columns:
            # Convert to datetime, coercing errors to NaT
            s = pd.to_datetime(df[field_name], errors='coerce')
            
            def make_dt_aware(dt):
                if pd.isnull(dt):
                    return None
                # Check if the datetime is naive (no timezone info)
                if is_naive(dt):
                    # Make it aware using the current Django timezone
                    return make_aware(dt, timezone=get_current_timezone())
                return dt

            # Apply the timezone conversion
            df[field_name] = s.apply(make_dt_aware)
            
    return df

def extract_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts columns prefixed with 'metadata.' into a single JSON/HStore field."""
    metadata_cols = [
        col for col in df.columns
        if str(col).lower().startswith("metadata.")
    ]

    if metadata_cols:
        def build_metadata_dict(row: pd.Series) -> Dict[str, Any]:
            # Use dictionary comprehension for efficiency and filtering None values
            return {
                col.split('.', 1)[1]: row[col]
                for col in metadata_cols
                if row[col] is not None and '.' in col
            }

        df["_metadata"] = df.apply(build_metadata_dict, axis=1)
        df.drop(columns=metadata_cols, inplace=True)
    
    return df

# --- Core Processing Functions ---

def read_and_preprocess_excel(obj: Importer, model: Type[Model], field_map: Dict[str, Field]) -> pd.DataFrame:
    """Reads the Excel file, handles basic cleaning, and normalizes column names."""
    
    # FIX: Use the fixed function which returns model field names
    date_like_field_names = get_field_names_by_internal_type(model, ["DateField", "DateTimeField"])

    # Read Excel.
    # IMPORTANT: The Excel column headers use verbose names. pandas' parse_dates requires column names.
    # We must pass the list of *verbose names* if we want pandas to parse them based on header name,
    # OR we read the file without parsing, then rename columns, then manually parse.
    # Since we need the original headers for `parse_dates`, let's get the VERBOSE NAMES.
    
    # Re-calculate the verbose names for date fields
    date_like_verbose_names = [
        field.verbose_name.upper() for field in model._meta.fields
        if field.name in date_like_field_names
    ]

    # The 'normalize_column_names' hasn't run yet, so we can't use 'field.name' for dtype
    # This dynamic dtype setting is complex and often better handled by forcing conversion *after* reading.
    # Let's simplify and rely on post-read cleanup/conversion.

    df = pd.read_excel(
        obj.document,
        sheet_name=0,
        # Pass the VERBOSE NAMES (in uppercase) to parse_dates
        parse_dates=date_like_verbose_names if date_like_verbose_names else None,
        # Remove dynamic dtype setting to simplify initial read and avoid mapping verbose/field names twice
        # The subsequent cleanup (df.replace) handles the raw values.
        dtype={"EMPLOYÉ": str, "NAME": str}
    )

    # Clean up NaNs and empty strings early
    # Replace common empty values with Python's None
    df.replace({np.nan: None, '': None, 'NaT': None}, inplace=True)

    # Normalize column names: verbose_name -> field_name
    df = normalize_column_names(df, field_map)
    
    return df

def process_data_frame(df: pd.DataFrame, model: Type[Model], field_map: Dict[str, Field], obj: Importer) -> List[Dict[str, Any]]:
    """Applies all complex data transformations to the DataFrame."""
    
    # 1. Convert related natural keys to Foreign Key IDs
    df = map_related_fields_to_ids(df, model, field_map)

    # 2. Add system fields (user IDs)
    if 'created_by_id' in [f.name for f in model._meta.fields]:
        df['created_by_id'] = obj.created_by.pk
    if 'updated_by_id' in [f.name for f in model._meta.fields]:
        df['updated_by_id'] = obj.created_by.pk

    # 3. Standardize Dates and Datetimes (timezone-aware)
    df = standardize_dates(df, model, field_map)
    
    # 4. Extract metadata
    df = extract_metadata(df)

    # 5. Final cleanup: replace any remaining NaNs with None for DB insertion
    df = df.where(pd.notnull(df), None)

    # 6. Convert to list of dictionaries for bulk creation
    return df.to_dict(orient='records')

def bulk_create_records(model: Type[Model], data: List[Dict[str, Any]], schema: str) -> None:
    """Performs the optimized database bulk creation."""
    
    # Filter for fields that exist on the model to prevent errors during instantiation
    model_field_names = {f.name for f in model._meta.fields}
    
    # Base dictionary for system fields common to all records
    extra_data = {}
    if 'sub_organization' in model_field_names:
        extra_data['sub_organization'] = schema
        
    if 'status' in model_field_names: 
        extra_data['status'] = 'APPROVED'

    records: List[Model] = []
    for row in data:
        # Merge filtered row data with extra system data
        merged_data = row | extra_data 

        # Instantiate the model object
        records.append(model(**merged_data))

    # The actual bulk insert, ignoring rows that conflict with unique constraints
    pre_bulk_save.send(sender=model, instances=records)
    with transaction.atomic():
        instances = model.objects.bulk_create(records, ignore_conflicts=True)
    post_bulk_save.send(sender=model, instances=instances, created=True)

# --- Celery Task ---

@shared_task(name='importer')
def importer(pk: int, schema: Optional[str] = None) -> None:
    """
    Celery task for handling data importation. 
    Improved for robustness, performance, and maintainability.
    """
    if schema:
        set_schema(schema)
        
    # 1. Initial Load and Validation
    try:
        obj: Importer = Importer.objects.get(pk=pk)
    except Importer.DoesNotExist:
        print(f"Importer object with pk={pk} does not exist.")
        return

    if not obj.document:
        handle_importer_error(obj, _('Le fichier d\'importation est manquant.'))
        return

    # User permission check
    permission = f'{obj.content_type.app_label}.add_{obj.content_type.model}'
    if not obj.created_by.has_perm(permission):
        error_msg = _('Vous n\'avez pas la permission d\'ajouter des données')
        handle_importer_error(obj, error_msg)
        send_failure_email(obj)
        return

    # Update status to processing
    update_importer_status(obj, ImporterStatus.PROCESSING)
    
    # Resolve Model and Field Map
    model: Type[Model] = obj.content_type.model_class()
    field_map: Dict[str, Field] = get_model_field_map(model)
    
    # 2. Core Import Logic with Robust Error Handling
    try:
        # Step 2a: Read and preprocess the Excel file
        df: pd.DataFrame = read_and_preprocess_excel(obj, model, field_map)

        # Step 2b: Process the DataFrame (Mapping, Date conversion, Metadata)
        data: List[Dict[str, Any]] = process_data_frame(df, model, field_map, obj)
        
        # Step 2c: Bulk create records in the database
        # FIX: Use obj.sub_organization if available, otherwise fallback.
        effective_schema = schema or getattr(obj, 'sub_organization', "Test") or "Test"
        bulk_create_records(model, data, effective_schema)

        # 3. Success Notification
        notify_user(
            obj, 
            _('Importation réussie'), 
            _('Les données ont été importées avec succès')
        )
        update_importer_status(obj, ImporterStatus.SUCCESS)

    except Exception as e:
        # 4. Failure Handling
        error_message = _(f'Une erreur inattendue est survenue pendant l\'importation: {str(e)}')
        handle_importer_error(obj, error_message)
        send_failure_email(obj)