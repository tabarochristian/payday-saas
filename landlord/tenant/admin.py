from django.contrib import admin
from tenant.models import Tenant

class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'full_name', 'email', 'phone', 'size', 'schema', 'is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone', 'schema', 'first_name', 'last_name')
    list_filter = ('size', 'is_active', 'created_at', 'updated_at')
    ordering = ('name',)
    readonly_fields = ('schema', 'is_active', 'created_at', 'updated_at')

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'

admin.site.register(Tenant, TenantAdmin)
