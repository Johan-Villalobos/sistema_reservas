from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.management.commands.seed_data import ESPACIOS_DEMO
from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico


class SeedDataEspaciosTests(TestCase):
    """La siembra de espacios es idempotente y crea uno por tipo."""

    def test_seed_data_creates_one_space_per_type(self):
        call_command("seed_data", stdout=StringIO())

        self.assertEqual(EspacioAcademico.objects.count(), len(ESPACIOS_DEMO))
        self.assertEqual(
            set(EspacioAcademico.objects.values_list("tipo", flat=True)),
            set(TipoEspacio.values),
        )
        for datos in ESPACIOS_DEMO:
            espacio = EspacioAcademico.objects.get(nombre=datos["nombre"])
            self.assertEqual(espacio.tipo, datos["tipo"])
            self.assertEqual(espacio.capacidad, datos["capacidad"])
            self.assertEqual(espacio.ubicacion, datos["ubicacion"])

    def test_seed_data_twice_does_not_duplicate_spaces(self):
        call_command("seed_data", stdout=StringIO())
        primeros = EspacioAcademico.objects.count()

        call_command("seed_data", stdout=StringIO())

        self.assertEqual(EspacioAcademico.objects.count(), primeros)

    def test_seed_data_respeta_espacio_desactivado(self):
        call_command("seed_data", stdout=StringIO())
        espacio = EspacioAcademico.objects.get(nombre="Auditorio Principal")
        espacio.activo = False
        espacio.save(update_fields=["activo"])

        call_command("seed_data", stdout=StringIO())

        espacio.refresh_from_db()
        self.assertFalse(espacio.activo)
        self.assertEqual(
            EspacioAcademico.objects.filter(
                nombre="Auditorio Principal"
            ).count(),
            1,
        )
