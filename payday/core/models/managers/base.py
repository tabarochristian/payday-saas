from django.db import models
from functools import reduce
from operator import or_
import pandas as pd

class CustomQuerySet(models.QuerySet):
    def related_to(self, user=None, *args, **kwargs):
        # Check if required parameters are provided
        # return super().all(*args, **kwargs)

        if user is None:
            return self.none()
    
        qs = super().all(*args, **kwargs)
        if user.is_superuser or user.is_staff:
            return qs
        
        # find in the model all field or subfield related to the user model
        related_fields = [
            field.name for field in qs.model._meta.fields
            if field.is_relation and field.related_model._meta.model_name.lower() == 'user'
        ]

        # find in the model all nested field related to the user model
        nested_related_fields = [
            f"{field.name}__{subfield.name}" for field in qs.model._meta.fields
            if field.is_relation for subfield in field.related_model._meta.fields
            if subfield.is_relation and subfield.related_model._meta.model_name.lower() == 'user'
        ]

        # combine related and nested related fields
        all_related_fields = related_fields + nested_related_fields
        
        # Apply filters on all related fields 
        filters = [models.Q(**{field: user}) for field in all_related_fields] 
        combined_filter = reduce(or_, filters) 
        return qs.filter(combined_filter)

    def to_table(self, fields=None):
        def get_field(field):
            return field.split('__')[0]

        fields = fields or self.model.list_display or [field.name for field in self.model._meta.fields]
        fields = [f'{field}__name' if self.model._meta.get_field(field).is_relation else field for field in fields]

        columns = [self.model._meta.get_field(get_field(field)).verbose_name for field in fields]
        df = pd.DataFrame.from_records(self.values(*fields))
        df.columns = columns

        return df.to_html(classes='col table table-striped table-bordered table-hover')

class CustomManager(models.Manager):
    def get_queryset(self):
        return CustomQuerySet(self.model, using=self._db)
    
    def related_to(self, user=None, *args, **kwargs):
        return self.get_queryset().related_to(user, *args, **kwargs)