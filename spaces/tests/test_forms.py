"""Pruebas del formulario de espacios.

Cubre REQ-ESP-002, REQ-ESP-003 y REQ-ESP-004.
"""

from django.test import TestCase

from spaces.choices import TipoEspacio
from spaces.forms import EspacioForm
from spaces.models import EspacioAcademico
from spaces.tests.utils import crear_espacio


class EspacioFormTests(TestCase):
    """Validación de creación y edición de espacios."""

    def datos(self, **cambios):
        datos = {
            "nombre": "Laboratorio Nuevo",
            "tipo": TipoEspacio.LABORATORIO,
            "capacidad": 25,
            "ubicacion": "Bloque B, piso 1",
            "descripcion": "Laboratorio de prácticas",
        }
        datos.update(cambios)
        return datos

    def test_req_esp_001_creacion_valida(self):
        formulario = EspacioForm(data=self.datos())

        self.assertTrue(formulario.is_valid(), formulario.errors)
        espacio = formulario.save()
        self.assertTrue(espacio.activo)
        self.assertEqual(espacio.nombre, "Laboratorio Nuevo")

    def test_req_esp_001_activo_no_es_un_campo_del_formulario(self):
        self.assertNotIn("activo", EspacioForm().fields)

    def test_req_esp_002_tipo_invalido_es_rechazado(self):
        formulario = EspacioForm(data=self.datos(tipo="BIBLIOTECA"))

        self.assertFalse(formulario.is_valid())
        self.assertIn("tipo", formulario.errors)
        self.assertFalse(
            EspacioAcademico.objects.filter(nombre="Laboratorio Nuevo").exists()
        )

    def test_req_esp_002_cada_tipo_permitido_se_registra(self):
        for indice, tipo in enumerate(TipoEspacio.values):
            with self.subTest(tipo=tipo):
                formulario = EspacioForm(
                    data=self.datos(nombre=f"Espacio {indice}", tipo=tipo)
                )
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.save().tipo, tipo)

    def test_req_esp_004_capacidad_cero_es_rechazada(self):
        formulario = EspacioForm(data=self.datos(capacidad=0))

        self.assertFalse(formulario.is_valid())
        self.assertIn("capacidad", formulario.errors)

    def test_req_esp_004_capacidad_negativa_es_rechazada(self):
        formulario = EspacioForm(data=self.datos(capacidad=-5))

        self.assertFalse(formulario.is_valid())
        self.assertIn("capacidad", formulario.errors)

    def test_req_esp_004_capacidad_decimal_es_rechazada(self):
        formulario = EspacioForm(data=self.datos(capacidad=1.5))

        self.assertFalse(formulario.is_valid())
        self.assertIn("capacidad", formulario.errors)

    def test_req_esp_003_nombre_duplicado_al_crear_es_rechazado(self):
        crear_espacio(nombre="Auditorio Principal")

        formulario = EspacioForm(
            data=self.datos(
                nombre="  AUDITORIO   PRINCIPAL ",
                tipo=TipoEspacio.AUDITORIO,
            )
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("nombre", formulario.errors)
        self.assertEqual(
            EspacioAcademico.objects.filter(
                nombre__iexact="auditorio principal"
            ).count(),
            1,
        )

    def test_req_esp_003_nombre_duplicado_al_renombrar_es_rechazado(self):
        crear_espacio(nombre="Laboratorio A")
        segundo = crear_espacio(nombre="Laboratorio B")

        formulario = EspacioForm(
            instance=segundo,
            data=self.datos(nombre="laboratorio a"),
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("nombre", formulario.errors)
        segundo.refresh_from_db()
        self.assertEqual(segundo.nombre, "Laboratorio B")

    def test_req_esp_001_edicion_valida_conserva_el_mismo_nombre(self):
        espacio = crear_espacio(nombre="Laboratorio A")

        formulario = EspacioForm(
            instance=espacio,
            data=self.datos(
                nombre="Laboratorio A",
                ubicacion="Bloque C",
                descripcion="Actualizada",
            ),
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        actualizado = formulario.save()
        self.assertEqual(actualizado.ubicacion, "Bloque C")
        self.assertEqual(actualizado.descripcion, "Actualizada")
