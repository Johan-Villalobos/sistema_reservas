"""Pruebas del modelo de espacios.

Cubre REQ-ESP-001, REQ-ESP-003 y REQ-ESP-004.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico
from spaces.tests.utils import crear_espacio


class EspacioAcademicoTests(TestCase):
    """Campos, estado, normalización, restricciones y queryset."""

    def test_req_esp_001_campos_y_estado_activo_por_defecto(self):
        espacio = EspacioAcademico.objects.create(
            nombre="Laboratorio de Química",
            tipo=TipoEspacio.LABORATORIO,
            capacidad=30,
            ubicacion="Bloque B, piso 2",
            descripcion="Laboratorio de prácticas",
        )

        recuperado = EspacioAcademico.objects.get(pk=espacio.pk)

        self.assertEqual(recuperado.nombre, "Laboratorio de Química")
        self.assertEqual(recuperado.tipo, TipoEspacio.LABORATORIO)
        self.assertEqual(recuperado.capacidad, 30)
        self.assertEqual(recuperado.ubicacion, "Bloque B, piso 2")
        self.assertEqual(recuperado.descripcion, "Laboratorio de prácticas")
        self.assertTrue(recuperado.activo)

    def test_req_esp_001_ubicacion_y_descripcion_son_editables(self):
        espacio = crear_espacio(ubicacion="Bloque A", descripcion="Original")

        espacio.ubicacion = "Bloque C"
        espacio.descripcion = "Actualizada"
        espacio.save()

        espacio.refresh_from_db()
        self.assertEqual(espacio.ubicacion, "Bloque C")
        self.assertEqual(espacio.descripcion, "Actualizada")

    def test_req_esp_001_normaliza_el_nombre_al_guardar(self):
        espacio = crear_espacio(nombre="  Auditorio   Principal ")

        self.assertEqual(espacio.nombre, "Auditorio Principal")

    def test_req_esp_001_str_devuelve_el_nombre(self):
        espacio = crear_espacio(nombre="Auditorio Principal")

        self.assertEqual(str(espacio), "Auditorio Principal")

    def test_req_esp_002_tipo_legible_usa_la_etiqueta_del_choices(self):
        espacio = crear_espacio(tipo=TipoEspacio.SALA_COMPUTO)

        self.assertEqual(espacio.tipo_legible, "Sala de cómputo")

    def test_req_esp_003_nombre_unico_insensible_a_mayusculas(self):
        crear_espacio(nombre="Auditorio Principal")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EspacioAcademico.objects.create(
                    nombre="AUDITORIO PRINCIPAL",
                    tipo=TipoEspacio.AUDITORIO,
                    capacidad=200,
                    ubicacion="Bloque A",
                )

        self.assertEqual(
            EspacioAcademico.objects.filter(
                nombre__iexact="auditorio principal"
            ).count(),
            1,
        )

    def test_req_esp_004_capacidad_cero_es_rechazada_por_la_base(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EspacioAcademico.objects.create(
                    nombre="Capacidad cero",
                    tipo=TipoEspacio.LABORATORIO,
                    capacidad=0,
                    ubicacion="Bloque A",
                )

    def test_req_esp_004_capacidad_negativa_es_rechazada_por_la_base(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EspacioAcademico.objects.create(
                    nombre="Capacidad negativa",
                    tipo=TipoEspacio.LABORATORIO,
                    capacidad=-5,
                    ubicacion="Bloque A",
                )

    def test_req_esp_006_queryset_activos_e_inactivos(self):
        activo = crear_espacio(nombre="Activo", activo=True)
        inactivo = crear_espacio(nombre="Inactivo", activo=False)

        self.assertIn(activo, EspacioAcademico.objects.activos())
        self.assertNotIn(inactivo, EspacioAcademico.objects.activos())
        self.assertIn(inactivo, EspacioAcademico.objects.inactivos())
        self.assertNotIn(activo, EspacioAcademico.objects.inactivos())
