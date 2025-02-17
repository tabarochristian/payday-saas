from django.contrib import admin
from tenant.models import Tenant

class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'plan', 'schema', 'is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone', 'schema', 'first_name', 'last_name')
    list_filter = ('plan', 'is_active', 'created_at', 'updated_at')
    readonly_fields = ('schema', 'created_at', 'updated_at')

    # Custom admin site header
    admin.site.site_header = "Payday.LandLord Administration"
    admin.site.site_title = "Payday.LandLord Admin Portal"
    admin.site.index_title = "Admin Portal"

admin.site.register(Tenant, TenantAdmin)