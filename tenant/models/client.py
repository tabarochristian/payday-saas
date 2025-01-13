from django_tenants.models import TenantMixin
from django.db import models

class Client(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)