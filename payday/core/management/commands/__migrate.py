from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Migrate command disabled for this environment."

    def handle(self, *args, **options):
        self.stdout.write(self.style.ERROR("Django migrate is disabled in this environment."))
