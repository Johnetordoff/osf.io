from django.db.models import Model
from django_extensions.management.commands import shell_plus
from django_extensions.management.utils import signalcommand


class Command(shell_plus.Command):
    def get_user_imports(self):
        return {}

    def get_grouped_imports(self, options):

        groups = {
            "models": {},
            "other": {},
        }
        groups.update({"user": self.get_user_imports()})
        # Import models and common django imports
        imports = shell_plus.Command.get_imported_objects(self, options)
        for name, object in imports.items():
            if isinstance(object, type) and issubclass(object, Model):
                groups["models"][name] = object
            else:
                groups["other"][name] = object

        return groups

    def get_imported_objects(self, options):
        # Merge all the values of grouped_imports
        imported_objects = {}
        for imports in self.grouped_imports.values():
            imported_objects.update(imports)
        return imported_objects

    @signalcommand
    def handle(self, *args, **options):
        options["quiet_load"] = False  # Don't show default shell_plus banner
        self.grouped_imports = self.get_grouped_imports(options)
        super(Command, self).handle(*args, **options)
