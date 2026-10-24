"""Utilidades compartidas por las pruebas de reservas."""

from datetime import date, time, timedelta

from accounts.tests.utils import crear_usuario
from reservations.models import EstadoReserva, Reserva
from spaces.tests.utils import crear_espacio

__all__ = [
    "crear_espacio",
    "crear_reserva",
    "crear_reserva_aprobada",
    "crear_usuario",
    "datos_solicitud",
]


def datos_solicitud(**cambios):
    """Datos válidos de solicitud con fecha de mañana y franja 10:00-11:00."""
    datos = {
        "fecha": date.today() + timedelta(days=1),
        "hora_inicio": time(10, 0),
        "hora_fin": time(11, 0),
        "motivo": "Reserva de prueba",
    }
    datos.update(cambios)
    return datos


def crear_reserva(
    *,
    espacio,
    solicitante=None,
    estado=EstadoReserva.PENDIENTE,
    **cambios,
):
    """Crea una reserva directamente por ORM para preparar escenarios.

    Se usa cuando la prueba necesita un estado distinto de ``PENDIENTE`` o una
    reserva que sería rechazada por la validación de disponibilidad al crearse.
    """
    datos = datos_solicitud(**cambios)
    if solicitante is None:
        solicitante = crear_usuario()
    return Reserva.objects.create(
        espacio=espacio,
        solicitante=solicitante,
        estado=estado,
        **datos,
    )


def crear_reserva_aprobada(*, espacio, **cambios):
    """Crea una reserva ``APROBADA`` con franja 10:00-12:00 por defecto."""
    cambios.setdefault("hora_inicio", time(10, 0))
    cambios.setdefault("hora_fin", time(12, 0))
    return crear_reserva(
        espacio=espacio,
        estado=EstadoReserva.APROBADA,
        **cambios,
    )
