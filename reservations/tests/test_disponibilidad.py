"""Pruebas de la regla de cruces y de las franjas ocupadas.

Cubre REQ-DIS-001, REQ-DIS-002, REQ-DIS-004, REQ-DIS-005 y la exclusión de la
propia reserva que usa la aprobación.
"""

from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from reservations.models import EstadoReserva
from reservations.services import validar_disponibilidad
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva,
    crear_reserva_aprobada,
    crear_usuario,
)


class ValidacionDisponibilidadTests(TestCase):
    """Matriz de cruces, estados, dimensiones y límites horarios."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio Disponibilidad")
        cls.otro_espacio = crear_espacio(nombre="Sala Alterna")
        cls.usuario = crear_usuario()
        cls.fecha = date.today() + timedelta(days=20)
        cls.otra_fecha = date.today() + timedelta(days=21)

    def crear_aprobada(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.usuario,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(12, 0),
        }
        datos.update(cambios)
        return crear_reserva_aprobada(**datos)

    def assert_conflicto(self, inicio, fin, *, espacio=None, fecha=None):
        with self.assertRaises(ValidationError) as contexto:
            validar_disponibilidad(
                espacio=espacio if espacio is not None else self.espacio,
                fecha=fecha if fecha is not None else self.fecha,
                hora_inicio=inicio,
                hora_fin=fin,
            )
        self.assertIn("hora_inicio", contexto.exception.message_dict)
        return contexto.exception

    def assert_sin_conflicto(self, inicio, fin, *, espacio=None, fecha=None):
        validar_disponibilidad(
            espacio=espacio if espacio is not None else self.espacio,
            fecha=fecha if fecha is not None else self.fecha,
            hora_inicio=inicio,
            hora_fin=fin,
        )

    # REQ-DIS-001: fórmula de cruce.

    def test_req_dis_001_cruce_total_es_rechazado(self):
        self.crear_aprobada()

        self.assert_conflicto(time(10, 0), time(12, 0))

    def test_req_dis_001_cruce_parcial_al_inicio_es_rechazado(self):
        self.crear_aprobada()

        self.assert_conflicto(time(9, 0), time(11, 0))

    def test_req_dis_001_cruce_parcial_al_final_es_rechazado(self):
        self.crear_aprobada()

        self.assert_conflicto(time(11, 0), time(13, 0))

    def test_req_dis_001_solicitud_contenida_es_rechazada(self):
        self.crear_aprobada()

        self.assert_conflicto(time(10, 30), time(11, 30))

    def test_req_dis_001_solicitud_contenedora_es_rechazada(self):
        self.crear_aprobada()

        self.assert_conflicto(time(9, 0), time(13, 0))

    def test_req_dis_001_solapamiento_minimo_es_rechazado(self):
        self.crear_aprobada(hora_inicio=time(10, 0), hora_fin=time(11, 0))

        self.assert_conflicto(time(10, 0), time(10, 1))

    # REQ-DIS-004: contigüidad y un minuto.

    def test_req_dis_004_contigua_anterior_es_aceptada(self):
        self.crear_aprobada()

        self.assert_sin_conflicto(time(9, 0), time(10, 0))

    def test_req_dis_004_contigua_posterior_es_aceptada(self):
        self.crear_aprobada()

        self.assert_sin_conflicto(time(12, 0), time(13, 0))

    def test_req_dis_004_solapamiento_de_un_minuto_es_rechazado(self):
        self.crear_aprobada(hora_inicio=time(10, 0), hora_fin=time(11, 0))

        self.assert_conflicto(time(10, 59), time(12, 0))

    def test_req_dis_004_extremos_del_horario_operativo_bloquean(self):
        self.crear_aprobada(hora_inicio=time(6, 0), hora_fin=time(22, 0))

        self.assert_conflicto(time(6, 0), time(7, 0))
        self.assert_conflicto(time(21, 0), time(22, 0))

    def test_req_dis_004_contiguedad_junto_al_cierre(self):
        self.crear_aprobada(hora_inicio=time(21, 0), hora_fin=time(22, 0))

        self.assert_sin_conflicto(time(20, 0), time(21, 0))

    def test_req_dis_004_contiguedad_junto_a_la_apertura(self):
        self.crear_aprobada(hora_inicio=time(6, 0), hora_fin=time(7, 0))

        self.assert_sin_conflicto(time(7, 0), time(8, 0))

    # REQ-DIS-002: solo APROBADA bloquea.

    def test_req_dis_002_aprobada_bloquea(self):
        self.crear_aprobada()

        self.assert_conflicto(time(10, 0), time(12, 0))

    def test_req_dis_002_pendiente_no_bloquea(self):
        crear_reserva(
            espacio=self.espacio,
            solicitante=self.usuario,
            fecha=self.fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            estado=EstadoReserva.PENDIENTE,
        )

        self.assert_sin_conflicto(time(10, 0), time(12, 0))

    def test_req_dis_002_rechazada_no_bloquea(self):
        crear_reserva(
            espacio=self.espacio,
            solicitante=self.usuario,
            fecha=self.fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            estado=EstadoReserva.RECHAZADA,
        )

        self.assert_sin_conflicto(time(10, 0), time(12, 0))

    def test_req_dis_002_cancelada_no_bloquea(self):
        crear_reserva(
            espacio=self.espacio,
            solicitante=self.usuario,
            fecha=self.fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            estado=EstadoReserva.CANCELADA,
        )

        self.assert_sin_conflicto(time(10, 0), time(12, 0))

    # REQ-DIS-005: independencia de espacio y fecha.

    def test_req_dis_005_mismo_horario_en_otro_espacio_es_permitido(self):
        self.crear_aprobada()

        self.assert_sin_conflicto(
            time(10, 0),
            time(12, 0),
            espacio=self.otro_espacio,
        )

    def test_req_dis_005_mismo_horario_en_otra_fecha_es_permitido(self):
        self.crear_aprobada()

        self.assert_sin_conflicto(
            time(10, 0),
            time(12, 0),
            fecha=self.otra_fecha,
        )

    def test_req_dis_009_excluir_reserva_evita_autoconflicto(self):
        reserva = self.crear_aprobada()

        validar_disponibilidad(
            espacio=self.espacio,
            fecha=self.fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            excluir_reserva=reserva.pk,
        )
