import os
import tempfile
import warnings
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, override_settings


class MigrationsTests(SimpleTestCase):
    """Aplica las migraciones sobre una base SQLite temporal y vacía."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_db = os.path.join(cls.temp_dir.name, "migrations.sqlite3")

        databases = dict(settings.DATABASES)
        databases["temp"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": cls.temp_db,
        }
        cls.override = override_settings(DATABASES=databases)
        with warnings.catch_warnings():
            # El alias alterno es intencional; se cierran las conexiones al limpiar.
            warnings.filterwarnings(
                "ignore",
                message="Overriding setting DATABASES",
                category=UserWarning,
            )
            cls.override.enable()
        cls.databases = {"default", "temp"}
        cls._reset_connections()

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        cls._reset_connections()
        cls.temp_dir.cleanup()

    @staticmethod
    def _reset_connections():
        """Fuerza a releer DATABASES tras el override."""
        connections.close_all()
        connections._settings = None
        connections.__dict__.pop("settings", None)

    def test_migrate_on_empty_database_leaves_no_pending_migrations(self):
        call_command("migrate", database="temp", verbosity=0, interactive=False)

        connection = connections["temp"]
        tables = set(connection.introspection.table_names())

        self.assertIn("accounts_usuario", tables)
        self.assertNotIn("auth_user", tables)

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.assertEqual(pending, [])

        salida = StringIO()
        call_command(
            "showmigrations",
            "--plan",
            database="temp",
            stdout=salida,
        )
        self.assertNotIn("[ ]", salida.getvalue())
