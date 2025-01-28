from tenant.models import Tenant
from celery import shared_task
import docker

@shared_task
def create_tenant_schema(_id):
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

@shared_task
def delete_tenant_schema(schema):
    # Initialize Docker client
    client = docker.from_env()

    # Get the Django container
    container = client.containers.get("payday-saas")

    # Run the migrate command
    cmd = f"python manage.py tenant {schema} lorem@ipsum.sit --delete"
    result = container.exec_run(cmd)

    # Decode the output
    output = result.output.decode("utf-8")

    # Return the output as a JSON response
    return {"output": output}