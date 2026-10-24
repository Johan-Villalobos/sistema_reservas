"""Pruebas del modelo de reservas.

Cubre REQ-SOL-002, REQ-SOL-010 y documenta la limitación de SQLite sobre
REQ-SOL-011.
"""

from datetime import time

from django.db import IntegrityError, transaction
from django.test import TestCase

from reservations.models import EstadoReserva, Reserva
from reservations.tests.utils import (
    crear_espacio,
    crear_usuario,
    datos_solicitud,
)


class ReservaModelTests(TestCase):
    """Valores por defecto, auditoría, relaciones y restricción de horas."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio()
        cls.solicitante = crear_usuario()
        cls.datos = datos_solicitud()

    def crear_reserva(self, **cambios):
        datos = {**self.datos, **cambios}
        return Reserva.objects.create(
            espacio=self.espacio,
            solicitante=self.solicitante,
            **datos,
        )

    def test_req_sol_002_estado_pendiente_y_creado_en_por_defecto(self):
        reserva = self.crear_reserva()

        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertIsNotNone(reserva.creado_en)
        self.assertIsNotNone(reserva.actualizado_en)

    def test_req_sol_002_str_incluye_espacio_y_fecha(self):
        reserva = self.crear_reserva()

        texto = str(reserva)

        self.assertIn(self.espacio.nombre, texto)
        self.assertIn(str(reserva.fecha), texto)
        self.assertIn("10:00-11:00", texto)

    def test_req_sol_002_relaciones_con_espacio_y_solicitante(self):
        reserva = self.crear_reserva()

        self.assertEqual(reserva.espacio, self.espacio)
        self.assertEqual(reserva.solicitante, self.solicitante)
        self.assertIn(reserva, self.espacio.reservas.all())
        self.assertIn(reserva, self.solicitante.reservas_solicitadas.all())

    def test_req_sol_010_horas_iguales_son_rechazadas_por_la_base(self):
        antes = Reserva.objects.count()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_reserva(hora_fin=self.datos["hora_inicio"])

        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_sol_010_horas_invertidas_son_rechazadas_por_la_base(self):
        antes = Reserva.objects.count()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_reserva(
                    hora_inicio=time(10, 0),
                    hora_fin=time(9, 0),
                )

        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_sol_011_escritura_directa_de_estado_no_esta_soportada(self):
        """SQLite permite escribir ``estado`` por ORM; no es una transición.

        La restricción de que el estado solo cambie mediante servicios es de
        contrato, no de base de datos. Esta prueba deja constancia de la
        limitación: una escritura directa no garantiza revisor, fecha de
        decisión ni historial, por lo que no se considera una transición
        válida del sistema.
        """
        reserva = self.crear_reserva()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

        reserva.estado = EstadoReserva.APROBADA
        reserva.save(update_fields=["estado"])
        reserva.refresh_from_db()

        self.assertEqual(reserva.estado, EstadoReserva.APROBADA)
