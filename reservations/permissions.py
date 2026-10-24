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
