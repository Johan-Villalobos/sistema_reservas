from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

# Se captura al importar el módulo, antes de que el runner de pruebas sustituya
# el nombre por el de la base de datos temporal de los tests.
NOMBRE_BASE_CONFIGURADO = Path(str(settings.DATABASES["default"]["NAME"]))


class SettingsTests(SimpleTestCase):
    """Comprueba la configuración regional y de base de datos exigida."""

    def test_database_engine_is_sqlite(self):
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )

    def test_database_name_is_db_sqlite3(self):
        self.assertEqual(NOMBRE_BASE_CONFIGURADO.name, "db.sqlite3")
        self.assertEqual(
            NOMBRE_BASE_CONFIGURADO,
            Path(settings.BASE_DIR) / "db.sqlite3",
        )

    def test_time_zone_is_bogota(self):
        self.assertEqual(settings.TIME_ZONE, "America/Bogota")

    def test_use_tz_is_enabled(self):
        self.assertTrue(settings.USE_TZ)

    def test_language_code_is_spanish_colombia(self):
        self.assertEqual(settings.LANGUAGE_CODE, "es-co")

    def test_custom_user_model_is_configured(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.Usuario")
