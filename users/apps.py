from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


def _create_default_roles(sender, **kwargs):
    # post_migrate fires once per app; wait for the last one so every app's permissions exist.
    # Adds any default role that is missing; existing roles are left as they are.
    last = [a for a in apps.get_app_configs() if a.models_module is not None][-1]
    if sender.name != last.name:
        return
    from users.roles import setup_default_roles
    setup_default_roles()


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        post_migrate.connect(_create_default_roles, dispatch_uid='users.default_roles')
