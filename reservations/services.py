"""Reglas de negocio de las solicitudes de reserva.

Concentra la lectura del horario operativo, la validación de la franja, la
fecha, el motivo y el estado del espacio, la detección de cruces, la consulta
de franjas ocupadas y la creación y aprobación transaccionales. Las vistas y
los formularios solo traducen los errores de este módulo.
"""

from datetime import datetime, time

from django.conf import settings
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from django.utils import timezone

from accounts.roles import Rol
from spaces.models import EspacioAcademico

from .models import EstadoReserva, Reserva

MENSAJE_HORA_FIN = "La hora de fin debe ser mayor que la hora de inicio."
MENSAJE_MOTIVO_VACIO = "El motivo es obligatorio."
MENSAJE_MOTIVO_LARGO = "El motivo no puede superar los 255 caracteres."
MENSAJE_ESPACIO_INACTIVO = "El espacio seleccionado no está activo."
MENSAJE_ESPACIO_INEXISTENTE = "El espacio seleccionado no existe."
MENSAJE_INICIO_PASADO = (
    "La fecha y la hora de inicio no pueden estar en el pasado."
)
MENSAJE_SOLO_PENDIENTES = (
    "Solo se pueden aprobar solicitudes en estado pendiente."
)
MENSAJE_APROBADOR_REQUERIDO = (
    "Solo un aprobador o un administrador puede aprobar solicitudes."
)


def obtener_horario_operativo():
    """Devuelve ``(apertura, cierre)`` a partir de los settings.

    Lanza ``ImproperlyConfigured`` si los valores no son horas ISO válidas o
    si la apertura no es anterior al cierre.
    """
    try:
        apertura = time.fromisoformat(settings.HORARIO_OPERATIVO_INICIO)
        cierre = time.fromisoformat(settings.HORARIO_OPERATIVO_FIN)
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(
            "HORARIO_OPERATIVO_INICIO y HORARIO_OPERATIVO_FIN deben ser "
            "horas ISO válidas (por ejemplo, '06:00')."
        ) from error

    if apertura >= cierre:
        raise ImproperlyConfigured(
            "HORARIO_OPERATIVO_INICIO debe ser anterior a "
            "HORARIO_OPERATIVO_FIN."
        )
    return apertura, cierre


def _normalizar_ahora(ahora):
    if ahora is None:
        return timezone.localtime()
    if timezone.is_naive(ahora):
        return timezone.make_aware(ahora, timezone.get_current_timezone())
    return ahora


def validar_solicitud(
    *,
    espacio,
    fecha,
    hora_inicio,
    hora_fin,
    motivo,
    ahora=None,
):
    """Valida una solicitud y lanza ``ValidationError`` con claves de campo."""
    errores = {}

    if hora_fin <= hora_inicio:
        errores["hora_fin"] = MENSAJE_HORA_FIN

    motivo_normalizado = (motivo or "").strip()
    if not motivo_normalizado:
        errores["motivo"] = MENSAJE_MOTIVO_VACIO
    elif len(motivo_normalizado) > 255:
        errores["motivo"] = MENSAJE_MOTIVO_LARGO

    if espacio is None or not getattr(espacio, "activo", False):
        errores["espacio"] = MENSAJE_ESPACIO_INACTIVO

    inicio = timezone.make_aware(
        datetime.combine(fecha, hora_inicio),
        timezone.get_current_timezone(),
    )
    if inicio < _normalizar_ahora(ahora):
        errores["hora_inicio"] = MENSAJE_INICIO_PASADO

    apertura, cierre = obtener_horario_operativo()
    if hora_inicio < apertura:
        errores["hora_inicio"] = (
            f"La hora de inicio no puede ser anterior a las {apertura:%H:%M}."
        )
    if hora_fin > cierre:
        errores["hora_fin"] = (
            f"La hora de fin no puede ser posterior a las {cierre:%H:%M}."
        )

    if errores:
        raise ValidationError(errores)


def validar_disponibilidad(
    *,
    espacio,
    fecha,
    hora_inicio,
    hora_fin,
    excluir_reserva=None,
):
    """Rechaza una franja que se cruce con una reserva aprobada.

    Dos reservas del mismo espacio y fecha se cruzan cuando
    ``inicio_A < fin_B`` y ``fin_A > inicio_B``. Las desigualdades estrictas
    permiten la contigüidad exacta. Solo las reservas ``APROBADA`` bloquean.

    ``excluir_reserva`` evita que una reserva se considere en conflicto
    consigo misma al revalidar una aprobación.
    """
    conflictos = Reserva.objects.filter(
        espacio=espacio,
        fecha=fecha,
        estado=EstadoReserva.APROBADA,
        hora_inicio__lt=hora_fin,
        hora_fin__gt=hora_inicio,
    )
    if excluir_reserva is not None:
        conflictos = conflictos.exclude(pk=excluir_reserva)

    conflicto = conflictos.order_by("hora_inicio").first()
    if conflicto is not None:
        raise ValidationError(
            {
                "hora_inicio": (
                    f"El espacio {espacio.nombre} ya está reservado el "
                    f"{fecha} de {conflicto.hora_inicio:%H:%M} a "
                    f"{conflicto.hora_fin:%H:%M}."
                )
            }
        )


def franjas_ocupadas(*, espacio, fecha):
    """Reservas aprobadas de un espacio y fecha, ordenadas por inicio.

    Limita los campos a la franja para no exponer al solicitante ni el motivo.
    La consulta se ejecuta en cada petición, sin caché.
    """
    return (
        Reserva.objects.filter(
            espacio=espacio,
            fecha=fecha,
            estado=EstadoReserva.APROBADA,
        )
        .order_by("hora_inicio")
        .only("hora_inicio", "hora_fin")
    )


@transaction.atomic
def crear_solicitud(
    *,
    espacio,
    solicitante,
    fecha,
    hora_inicio,
    hora_fin,
    motivo,
):
    """Crea una solicitud ``PENDIENTE`` revalidando dentro de la transacción.

    El estado inicial no es parametrizable: toda creación pasa por este
    servicio y siempre escribe ``EstadoReserva.PENDIENTE``.
    """
    if espacio is None:
        raise ValidationError({"espacio": MENSAJE_ESPACIO_INEXISTENTE})

    espacio_actual = (
        EspacioAcademico.objects.select_for_update()
        .filter(pk=espacio.pk)
        .first()
    )
    if espacio_actual is None:
        raise ValidationError({"espacio": MENSAJE_ESPACIO_INEXISTENTE})

    validar_solicitud(
        espacio=espacio_actual,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=motivo,
    )

    validar_disponibilidad(
        espacio=espacio_actual,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
    )

    return Reserva.objects.create(
        espacio=espacio_actual,
        solicitante=solicitante,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=(motivo or "").strip(),
        estado=EstadoReserva.PENDIENTE,
    )


@transaction.atomic
def aprobar_reserva(*, reserva, actor):
    """Aprueba una solicitud pendiente revalidando la disponibilidad.

    La reserva se recarga con ``select_for_update()`` y toda la operación
    corre en una transacción atómica: la comprobación de estado, la
    revalidación del cruce y la escritura de ``APROBADA`` forman una sola
    unidad. Si hay conflicto se lanza ``ValidationError`` y la solicitud
    permanece en su estado anterior.

    ``select_for_update()`` se conserva para PostgreSQL, pero SQLite lo
    ignora y no ofrece bloqueo pesimista real; la ventana de carrera residual
    se documenta como limitación conocida. El servicio exige un actor con rol
    ``APROBADOR`` o ``ADMINISTRADOR`` como defensa en profundidad.
    """
    reserva_actual = (
        Reserva.objects.select_for_update()
        .select_related("espacio")
        .filter(pk=reserva.pk)
        .first()
    )
    if reserva_actual is None:
        raise ValidationError({"estado": "La solicitud ya no existe."})

    if reserva_actual.estado != EstadoReserva.PENDIENTE:
        raise ValidationError({"estado": MENSAJE_SOLO_PENDIENTES})

    if not getattr(actor, "is_authenticated", False) or actor.rol not in (
        Rol.APROBADOR,
        Rol.ADMINISTRADOR,
    ):
        raise PermissionDenied(MENSAJE_APROBADOR_REQUERIDO)

    validar_disponibilidad(
        espacio=reserva_actual.espacio,
        fecha=reserva_actual.fecha,
        hora_inicio=reserva_actual.hora_inicio,
        hora_fin=reserva_actual.hora_fin,
        excluir_reserva=reserva_actual.pk,
    )

    reserva_actual.estado = EstadoReserva.APROBADA
    reserva_actual.save(update_fields=["estado", "actualizado_en"])
    return reserva_actual
