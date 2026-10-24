"""Permisos por objeto para las solicitudes de reserva."""

from accounts.roles import Rol


def puede_ver_solicitud(usuario, reserva):
    """Indica si ``usuario`` puede consultar el detalle de ``reserva``.

    Puede verla su solicitante y cualquier usuario autenticado con rol
    ``APROBADOR`` o ``ADMINISTRADOR``.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.pk == reserva.solicitante_id:
        return True
    return usuario.rol in (Rol.APROBADOR, Rol.ADMINISTRADOR)


def puede_decidir_reserva(usuario, reserva):
    """Indica si ``usuario`` puede aprobar o rechazar ``reserva``.

    Requiere autenticación, rol ``APROBADOR`` o ``ADMINISTRADOR`` y que el
    usuario no sea el solicitante. El estado de la reserva no forma parte de
    este permiso: una solicitud no pendiente sigue siendo visible y su intento
    de decisión produce un mensaje de transición, no un 403.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.rol not in (Rol.APROBADOR, Rol.ADMINISTRADOR):
        return False
    return usuario.pk != reserva.solicitante_id


def es_administrador(usuario):
    """Indica si ``usuario`` está autenticado y tiene rol ``ADMINISTRADOR``."""
    return (
        getattr(usuario, "is_authenticated", False)
        and usuario.rol == Rol.ADMINISTRADOR
    )


def puede_cancelar_reserva(usuario, reserva):
    """Indica si ``usuario`` puede cancelar ``reserva``.

    Solo el solicitante o un administrador. El estado y la hora de inicio no
    forman parte de este permiso: son reglas de negocio que producen un mensaje
    de error, no un 403.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    return (
        usuario.pk == reserva.solicitante_id
        or usuario.rol == Rol.ADMINISTRADOR
    )


def puede_ver_historial(usuario, reserva):
    """Indica si ``usuario`` puede consultar el historial de ``reserva``.

    Un aprobador no propietario puede ver el detalle de la solicitud, pero no
    su historial.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    return (
        usuario.pk == reserva.solicitante_id
        or usuario.rol == Rol.ADMINISTRADOR
    )

