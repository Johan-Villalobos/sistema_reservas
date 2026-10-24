from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Usuario
from accounts.roles import Rol
from core.management.commands.seed_data import CONTRASENA_DEMO, USUARIOS_DEMO


class SeedDataTests(TestCase):
    """Comprueba la idempotencia y el resumen del comando seed_data."""

    def test_seed_data_twice_does_not_duplicate_users(self):
        call_command("seed_data", stdout=StringIO())
        primeros = Usuario.objects.count()

        call_command("seed_data", stdout=StringIO())

        self.assertEqual(Usuario.objects.count(), primeros)
        self.assertEqual(Usuario.objects.count(), len(USUARIOS_DEMO))

    def test_seed_data_creates_one_user_per_role(self):
        call_command("seed_data", stdout=StringIO())

        roles = set(Usuario.objects.values_list("rol", flat=True))

        self.assertEqual(roles, set(Rol.values))
        for datos in USUARIOS_DEMO:
            usuario = Usuario.objects.get(username=datos["username"])
            self.assertEqual(usuario.rol, datos["rol"])
            self.assertEqual(usuario.email, datos["email"])
            self.assertTrue(usuario.check_password(CONTRASENA_DEMO))

    def test_seed_data_does_not_overwrite_existing_users(self):
        call_command("seed_data", stdout=StringIO())
        admin = Usuario.objects.get(username="admin")
        admin.nombre_completo = "Administrador Editado"
        admin.set_password("OtraClave123!")
        admin.save()

        call_command("seed_data", stdout=StringIO())

        admin.refresh_from_db()
        self.assertEqual(admin.nombre_completo, "Administrador Editado")
        self.assertTrue(admin.check_password("OtraClave123!"))

    def test_seed_data_reports_created_and_existing_counts(self):
        salida = StringIO()
        call_command("seed_data", stdout=salida)
        primer_resumen = salida.getvalue()

        salida = StringIO()
        call_command("seed_data", stdout=salida)
        segundo_resumen = salida.getvalue()

        self.assertIn("3 creados", primer_resumen)
        self.assertIn("0 existentes", primer_resumen)
        self.assertIn("0 creados", segundo_resumen)
        self.assertIn("3 existentes", segundo_resumen)
