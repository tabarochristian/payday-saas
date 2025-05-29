
from django.contrib.contenttypes.models import ContentType
from typing import Dict, Any, Union, List
from django.apps import apps

def get_rls_filters(user, model_class: type) -> Dict[str, Any]:
    """
    Get all dynamic row-level filters for this user/model.
    Returns: Dict of filters to apply to queryset.
    """
    RowLevelSecurity = apps.get_model('core', model_name='rowlevelsecurity')
    content_type = ContentType.objects.get_for_model(model_class)

    rls_rules = (
        RowLevelSecurity.objects
        .filter(
            content_type=content_type,
            user__in=user.groups.all() or [],
        )
        .values_list('field', 'value')
    )

    return {field: value for field, value in rls_rules}