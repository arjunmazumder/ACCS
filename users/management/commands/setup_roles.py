from django.core.management.base import BaseCommand

from users.roles import setup_default_roles


class Command(BaseCommand):
    help = "Create the default customer and staff roles with their permissions. --reset puts existing default roles back to their defaults."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Overwrite the permissions of existing default roles')

    def handle(self, *args, reset=False, **options):
        setup_default_roles(reset=reset, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS('Roles are ready.'))
