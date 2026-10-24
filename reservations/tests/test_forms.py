"""Pruebas del formulario de solicitud de reserva.

Cubre REQ-SOL-003, REQ-SOL-004, REQ-SOL-005, REQ-SOL-006 y REQ-SOL-007.
"""

from datetime import date, time, timedelta

from django.test import TestCase

from reservations.forms import SolicitudReservaForm
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva_aprobada,
    crear_usuario,
    datos_solicitud,
)


class SolicitudReservaFormTests(TestCase):
    """Campos expuestos, selector de espacios y validaciones mapeadas."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = crear_usuario()
        cls.activo = crear_espacio(nombre="Laboratorio Formulario")
        cls.inactivo = crear_espacio(
            nombre="Laboratorio Inactivo",
            activo=False,
        )

    def datos(self, **cambios):
        datos = {
            "espacio": self.activo.pk,
            **datos_solicitud(),
        }
        datos.update(cambios)
        return datos

    def test_req_sol_003_campos_expuestos_y_sin_fecha_fin(self):
        formulario = SolicitudReservaForm()

        self.assertEqual(
            set(formulario.fields),
            {"espacio", "fecha", "hora_inicio", "hora_fin", "motivo"},
        )
        self.assertNotIn("fecha_fin", formulario.fields)
        self.assertNotIn("solicitante", formulario.fields)
        self.assertNotIn("estado", formulario.fields)
        self.assertNotIn("creado_en", formulario.fields)

    def test_req_sol_005_selector_solo_ofrece_espacios_activos(self):
        opciones = SolicitudReservaForm().fields["espacio"].queryset

        self.assertIn(self.activo, opciones)
        self.assertNotIn(self.inactivo, opciones)

    def test_req_sol_005_espacio_inactivo_enviado_manualmente_es_rechazado(self):
        formulario = SolicitudReservaForm(
            data=self.datos(espacio=self.inactivo.pk)
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("espacio", formulario.errors)

    def test_req_sol_006_motivo_vacio_es_rechazado(self):
        for motivo in ("", "   "):
            with self.subTest(motivo=repr(motivo)):
                formulario = SolicitudReservaForm(
                    data=self.datos(motivo=motivo)
                )
                self.assertFalse(formulario.is_valid())
                self.assertIn("motivo", formulario.errors)

    def test_req_sol_006_motivo_de_255_caracteres_es_aceptado(self):
        formulario = SolicitudReservaForm(
            data=self.datos(motivo="x" * 255)
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)

    def test_req_sol_006_motivo_de_256_caracteres_es_rechazado(self):
        formulario = SolicitudReservaForm(
            data=self.datos(motivo="x" * 256)
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("motivo", formulario.errors)

    def test_req_sol_003_hora_fin_igual_a_inicio_es_rechazada(self):
        formulario = SolicitudReservaForm(
            data=self.datos(hora_inicio="10:00", hora_fin="10:00")
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("hora_fin", formulario.errors)

    def test_req_sol_003_hora_fin_anterior_a_inicio_es_rechazada(self):
        formulario = SolicitudReservaForm(
            data=self.datos(hora_inicio="12:00", hora_fin="11:00")
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("hora_fin", formulario.errors)

    def test_req_sol_004_fecha_pasada_es_rechazada_en_hora_inicio(self):
        formulario = SolicitudReservaForm(
            data=self.datos(fecha=date.today() - timedelta(days=1))
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("hora_inicio", formulario.errors)

    def test_req_sol_007_horario_fuera_del_rango_se_asocia_a_su_campo(self):
        muy_temprano = SolicitudReservaForm(
            data=self.datos(hora_inicio="05:59", hora_fin="07:00")
        )
        muy_tarde = SolicitudReservaForm(
            data=self.datos(hora_inicio="21:00", hora_fin="22:01")
        )

        self.assertIn("hora_inicio", muy_temprano.errors)
        self.assertIn("hora_fin", muy_tarde.errors)

    def test_req_sol_007_ayuda_del_horario_operativo(self):
        formulario = SolicitudReservaForm()

        self.assertIn(
            "06:00 a 22:00",
            formulario.fields["hora_inicio"].help_text,
        )
        self.assertIn(
            "06:00 a 22:00",
            formulario.fields["hora_fin"].help_text,
        )

    def test_req_dis_003_formulario_muestra_conflicto_en_hora_inicio(self):
        datos = self.datos(hora_inicio="11:00", hora_fin="13:00")
        crear_reserva_aprobada(
            espacio=self.activo,
            solicitante=self.usuario,
            fecha=datos["fecha"],
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )

        formulario = SolicitudReservaForm(data=datos)

        self.assertFalse(formulario.is_valid())
        self.assertIn("hora_inicio", formulario.errors)
        mensaje = formulario.errors["hora_inicio"][0]
        self.assertIn(self.activo.nombre, mensaje)
        self.assertIn(str(datos["fecha"]), mensaje)
        self.assertIn("10:00", mensaje)
        self.assertIn("12:00", mensaje)
