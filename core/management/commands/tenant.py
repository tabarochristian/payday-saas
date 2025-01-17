from django.core.management.base import BaseCommand
from core import utils

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema'

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to run migrations on')

    def handle(self, *args, **kwargs):
        schema = kwargs['schema']

        utils.create_schema_if_not_exists(schema)
        utils.set_schema(schema)

        self.stdout.write(self.style.SUCCESS(f'Running migrations for schema "{schema}"...'))
        from django.core.management import call_command
        call_command('migrate')

        # load default menu

        self.stdout.write(self.style.SUCCESS(f'Successfully ran migrations for schema "{schema}".'))