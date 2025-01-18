# celery_worker.py
from models import Organization
from extensions import db
import docker

# Define a sample task
def create_organization_schema(obj):
    _id = obj.get('id', None)
    if not _id: 
        return
    
    organization = Organization.query.get(_id)
    organization.is_created = True
    db.session.commit()

    # Initialize Docker client
    client = docker.from_env()

    # Get the Django container
    container = client.containers.get("payday-saas")

    # Run the migrate command
    tenant = organization.schema
    email = organization.email

    cmd = f"python manage.py tenant {tenant} {email}"
    result = container.exec_run(cmd)

    # Decode the output
    output = result.output.decode("utf-8")

    # Return the output as a JSON response
    return {"output": output}