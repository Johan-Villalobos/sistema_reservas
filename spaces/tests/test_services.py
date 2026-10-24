"""Pruebas de las reglas de negocio de espacios, sin cliente HTTP."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico
from spaces.services import (
    MENSAJE_NOMBRE_DUPLICADO,
    actualizar_espacio,
    crear_espacio,
    desactivar_espacio,
    normalizar_nombre,
)
from spaces.tests.utils import crear_espacio as crear_espacio_directo


class ServicioEspaciosTests(TestCase):
    """Normalización, duplicados, capacidad y desactivación lógica."""

    def test_normalizar_nombre_recorta_y_colapsa_espacios(self):
        self.assertEqual(
            normalizar_nombre("  Auditorio   Principal "),
            "Auditorio Principal",
        )

    def test_req_esp_003_crear_espacio_normaliza_y_persiste(self):
        espacio = crear_espacio(
            nombre="  Laboratorio   de   Química ",
            tipo=TipoEspacio.LABORATORIO,
            capacidad=30,
            ubicacion="Bloque B",
        )

        self.assertIsInstance(espacio, EspacioAcademico)
        self.assertEqual(espacio.nombre, "Laboratorio de Química")

    def test_req_esp_003_crear_con_nombre_duplicado_falla(self):
        crear_espacio_directo(nombre="Auditorio Principal")

        with self.assertRaisesMessage(ValidationError, MENSAJE_NOMBRE_DUPLICADO):
            crear_espacio(
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

    def test_req_esp_004_crear_con_capacidad_invalida_falla(self):
        for capacidad in (0, -5, 1.5, True):
            with self.subTest(capacidad=capacidad):
                with self.assertRaises(ValidationError):
                    crear_espacio(
                        nombre=f"Capacidad {capacidad}",
                        tipo=TipoEspacio.LABORATORIO,
                        capacidad=capacidad,
                        ubicacion="Bloque A",
                    )
        self.assertFalse(
            EspacioAcademico.objects.filter(nombre__startswith="Capacidad ").exists()
        )

    def test_req_esp_002_crear_con_tipo_invalido_falla(self):
        with self.assertRaises(ValidationError):
            crear_espacio(
                nombre="Tipo inválido",
                tipo="BIBLIOTECA",
                capacidad=10,
                ubicacion="Bloque A",
            )

        self.assertFalse(
            EspacioAcademico.objects.filter(nombre="Tipo inválido").exists()
        )

    def test_req_esp_001_actualizar_espacio_conserva_los_demas_campos(self):
        espacio = crear_espacio_directo(
            nombre="Laboratorio A",
            capacidad=25,
            ubicacion="Bloque B",
            descripcion="Original",
        )

        actualizado = actualizar_espacio(
            espacio,
            datos_validados={
                "ubicacion": "Bloque C",
                "descripcion": "Actualizada",
            },
        )

        self.assertEqual(actualizado.nombre, "Laboratorio A")
        self.assertEqual(actualizado.capacidad, 25)
        self.assertEqual(actualizado.ubicacion, "Bloque C")
        self.assertEqual(actualizado.descripcion, "Actualizada")

    def test_req_esp_003_actualizar_con_nombre_de_otro_espacio_falla(self):
        primero = crear_espacio_directo(nombre="Laboratorio A")
        segundo = crear_espacio_directo(nombre="Laboratorio B")

        with self.assertRaisesMessage(ValidationError, MENSAJE_NOMBRE_DUPLICADO):
            actualizar_espacio(
                segundo,
                datos_validados={"nombre": "laboratorio a"},
            )

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.nombre, "Laboratorio A")
        self.assertEqual(segundo.nombre, "Laboratorio B")

    def test_req_esp_004_actualizar_con_capacidad_invalida_falla(self):
        espacio = crear_espacio_directo(capacidad=25)

        with self.assertRaises(ValidationError):
            actualizar_espacio(
                espacio,
                datos_validados={"capacidad": 0},
            )

        espacio.refresh_from_db()
        self.assertEqual(espacio.capacidad, 25)

    def test_req_esp_006_desactivar_conserva_el_registro(self):
        espacio = crear_espacio_directo(activo=True)

        desactivar_espacio(espacio)

        espacio.refresh_from_db()
        self.assertFalse(espacio.activo)
        self.assertTrue(EspacioAcademico.objects.filter(pk=espacio.pk).exists())

    def test_req_esp_006_desactivar_es_idempotente(self):
        espacio = crear_espacio_directo(activo=True)
        desactivar_espacio(espacio)

        desactivar_espacio(espacio)

        espacio.refresh_from_db()
        self.assertFalse(espacio.activo)
        self.assertEqual(
            EspacioAcademico.objects.filter(pk=espacio.pk).count(),
            1,
        )
