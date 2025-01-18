from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class AuthBackend(ModelBackend):
    def _get_group_permissions(self, user_obj):
        user_groups_field = get_user_model()._meta.get_field("groups")
        user_groups_query = "groups__%s" % user_groups_field.related_query_name()
        return Permission.objects.filter(**{user_groups_query: user_obj})