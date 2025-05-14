from django.db import connection
from django.db.utils import DatabaseError
from django.core.management import call_command
from django.contrib.auth import get_user_model
from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type, before_sleep_log
import logging
from typing import Optional

logger = logging.getLogger(__name__)
User = get_user_model()

class SchemaManager:
    """
    Manages database schema creation, migrations, and superuser creation for tenants.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((DatabaseError,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_schema(self, schema: str) -> None:
        """
        Create a new database schema.
        """
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{schema}"')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((DatabaseError,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def apply_migrations(self, schema: str) -> None:
        """
        Apply Django migrations to the schema.
        """
        from core.utils import set_schema
        set_schema(schema)
        call_command('migrate', verbosity=0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((DatabaseError,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_superuser(self, schema: str, email: str, password: str) -> User:
        """
        Create a superuser for the tenant.
        """
        from core.utils import set_schema
        set_schema(schema)
        username = email.split('@')[0]
        user = User.objects.create_superuser(
            email=email,
            # username=username,
            password=password,
            is_active=True,
            is_staff=True
        )
        return user

    def is_schema_unique(self, schema: str) -> bool:
        """
        Check if the schema name is unique in the database.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", [schema])
            return not cursor.fetchone()