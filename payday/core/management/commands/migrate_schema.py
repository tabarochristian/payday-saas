from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connection, transaction
from django.db import DEFAULT_DB_ALIAS


class Command(MigrateCommand):
    help = "Run migrations for a specific schema, or all application schemas if none is provided. Designed for PostgreSQL multi-tenant systems."

    def add_arguments(self, parser):
        # Add the standard arguments from the base Migrate command
        # This will include things like --app-label, --name, --fake, etc.
        super().add_arguments(parser)
        
        # Add the custom schema argument
        parser.add_argument(
            "--schema",
            type=str,
            help="Specify the schema to apply migrations to. If omitted, migrations will be run on all application schemas.",
        )
        
        # NOTE: The --database argument is REMOVED here, allowing it to default 
        # to DEFAULT_DB_ALIAS (usually 'default') via the inherited handle method.


    def handle(self, *args, **options):
        schema = options.get("schema")
        
        # The database alias is implicitly the default one for the connection object
        database = options.get('database') or DEFAULT_DB_ALIAS 

        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.ERROR(
                "Error: This command is designed for PostgreSQL multi-schema environments only."))
            # Still call super().handle() to execute standard migration on the single default database
            super().handle(*args, **options) 
            return

        if schema:
            # Case 1: Schema is provided. Run migration only for that schema.
            schemas_to_migrate = [schema]
            self.stdout.write(self.style.NOTICE(f"Applying migrations to specified schema: '{schema}'."))
        else:
            # Case 2: Schema is NOT provided. Fetch all application schemas.
            
            # --- SCHEMA EXCLUSION LIST ---
            # Exclude standard system schemas and the default user schema ('public').
            system_schemas = [
                'pg_toast', 
                'pg_temp_1', 
                'pg_catalog', 
                'information_schema', 
                'public',
                'lago'
            ]
            
            with connection.cursor() as cursor:
                # Query all schemas, excluding system/default schemas and templates.
                cursor.execute("""
                    SELECT nspname 
                    FROM pg_catalog.pg_namespace 
                    WHERE nspname NOT IN %s 
                      AND nspname NOT LIKE 'tenant_template%%' 
                    ORDER BY nspname;
                """, (tuple(system_schemas),))
                
                # Fetching application schemas from the database
                schemas_to_migrate = [row[0] for row in cursor.fetchall()]
                
            self.stdout.write(self.style.NOTICE(f"Found {len(schemas_to_migrate)} application schemas to migrate."))
            if not schemas_to_migrate:
                self.stdout.write(self.style.WARNING("No application schemas found. Exiting."))
                return

        
        # --- Migration Loop ---
        
        # Copy original options, excluding 'schema' as it's not a standard Django migrate option
        migrate_options = options.copy()
        # Ensure we do not pass the custom '--schema' argument to the base migrate command
        migrate_options.pop('schema', None) 
        
        for current_schema in schemas_to_migrate:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n--- Applying migrations to schema: {current_schema} ---"))

            # Use a transaction block on the default database connection
            with transaction.atomic(using=database):
                with connection.cursor() as cursor:
                    # 1. Set the search path to the current schema for the current connection
                    cursor.execute(f"SET search_path TO {current_schema}, public;")

                    
                    # 2. Run the actual Django migrate command logic
                    try:
                        # Call the original migrate command handler
                        super().handle(*args, **migrate_options)
                        self.stdout.write(self.style.SUCCESS(
                            f"Successfully applied migrations to schema: {current_schema}"))
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"ERROR applying migrations to schema {current_schema}: {e}"))
                        # Re-raise the exception to roll back the current transaction and stop the process.
                        raise e 
                        
        self.stdout.write(self.style.SUCCESS("\n--- Migration process complete ---"))