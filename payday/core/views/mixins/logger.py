from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.contrib.admin.models import LogEntry
from django.forms.models import model_to_dict
from django.utils.encoding import force_str

class LoggerMixin:
    """
    A mixin that provides logging functionality. It offers methods for retrieving logs 
    for a model instance and generating a detailed change message when comparing an 
    old instance with an updated one.

    The mixin assumes that the implementing class provides:
      - self.request containing the current HttpRequest.
      - self.kwargs with URL parameters including the primary key (pk).
      - A method get_content_type() that returns the ContentType of the model.
    """

    def logs(self):
        """
        Retrieves log entries for the current object based on its content type and primary key.

        Returns:
            QuerySet: A QuerySet of log entries with only 'change_message' and 'action_time' fields.
        """
        object_pk = self.kwargs.get('pk')
        content_type = self.get_content_type()
        return LogEntry.objects.filter(
            content_type=content_type,
            object_id=object_pk
        ).values('change_message', 'action_time')
    
    def generate_change_message(self, old_instance, new_instance):
        """
        Generate a change message that summarizes differences between the old and new model instances.
        
        Args:
            old_instance: The original model instance.
            new_instance: The updated model instance.
        
        Returns:
            str or None: A semicolon-separated string describing which fields have changed,
                         or None if no changes occurred.
        """
        # Retrieve the list of field names from the new instance.
        field_names = [field.name for field in new_instance._meta.fields]
        # Convert both instances into dictionaries.
        old_data = model_to_dict(old_instance, fields=field_names)
        new_data = model_to_dict(new_instance, fields=field_names)
        
        change_messages = []
        # Compare field values in both dictionaries.
        for field in field_names:
            old_value = old_data.get(field)
            new_value = new_data.get(field)
            if old_value != new_value:
                # Retrieve a human-readable field name from the model's meta.
                verbose_name = new_instance._meta.get_field(field).verbose_name
                message = _(f"Field '{verbose_name}' changed from '{old_value}' to '{new_value}'.")
                change_messages.append(message)
        
        return "; ".join(change_messages) if change_messages else None

    def log(self, model, form, action, change_message):
        """
        Log an action using Django's LogEntry system.

        Args:
            model: The model class of the object being logged.
            form: The form instance associated with the object.
            action: The action flag (e.g., ADDITION, DELETION, or CHANGE).
            change_message: A string describing the changes made.
        
        Returns:
            LogEntry: The created log entry or None if change_message is None.
        """
        if not change_message:
            return
        return LogEntry.objects.log_action(
            user_id=self.request.user.id,
            content_type_id=ContentType.objects.get_for_model(model).id,
            object_id=form.instance.pk,
            object_repr=force_str(form.instance),
            action_flag=action,
            change_message=change_message
        )
# The LoggerMixin provides methods for retrieving logs, generating change messages, and logging actions.