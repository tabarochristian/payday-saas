def upload_directory_file(instance, filename):
    from core.middleware import TenantMiddleware
    schema = TenantMiddleware.get_schema() or 'payday'
    return '{0}/{1}/{2}/{3}'.format(schema, instance._meta.app_label, instance._meta.model_name, filename)