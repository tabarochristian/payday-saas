from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connection


class Command(MigrateCommand):
    help = "Run migrations for a specific schema."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--schema",
            type=str,
            help="Specify the schema to apply migrations to",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")

        if schema:
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema};")

        super().handle(*args, **options)
