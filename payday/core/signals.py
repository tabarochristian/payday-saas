from django.dispatch import Signal

# Signal dispatched just before a bulk save operation starts
# sender: The model class being saved
# instances: The list of model instances (or QuerySet for update/delete)
pre_bulk_save = Signal()

# Signal dispatched just after a bulk save operation finishes
# sender: The model class being saved
# instances: The list of model instances (or QuerySet for update/delete)
post_bulk_save = Signal()