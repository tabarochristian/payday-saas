from tenant.models import Tenant
from celery import shared_task
import docker

@shared_task(name="create_tenant_schema")
def create_tenant_schema(obj):
    _id = obj.get('id', None)
    if not _id: 
        return
    
    tenant = Tenant.objects.filter(id=_id)
    tenant = tenant.first()

    if not tenant:
        return

    # Initialize Docker client
    client = docker.from_env()

    # Get the Django container
    container = client.containers.get("payday-saas")

    # Run the migrate command

    cmd = f"python manage.py tenant {tenant.schema} {tenant.email}"
    result = container.exec_run(cmd)

    # Update the organization status
    tenant.is_active = True
    tenant.save()

    # Decode the output
    output = result.output.decode("utf-8")

    # Return the output as a JSON response
    return {"output": output}