from django.contrib.contenttypes.models import ContentType
from typing import Dict, Any, Union, List

def get_cls_access(user, model_class: type) -> Dict[str, str]:
    """
    Get field-level access control for this user/model.
    Returns: Dict of field → access_level
    """
    ColumnLevelSecurity = apps.get_model('core', model_name='columnlevelsecurity')
    content_type = ContentType.objects.get_for_model(model_class)

    cls_rules = (
        ColumnLevelSecurity.objects
        .filter(
            content_type=content_type,
            user__in=user.groups.all() or []
        )
        .values_list('field_name', 'access')
    )

    return dict(cls_rules)