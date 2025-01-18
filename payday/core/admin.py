# your_app_name/admin.py
from django.contrib.auth.models import Group
from django.contrib import admin

# Unregister the Group model
admin.site.unregister(Group)