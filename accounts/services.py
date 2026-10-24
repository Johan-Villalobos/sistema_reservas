"""Reglas de negocio de cuentas.

Concentra la invariante de "al menos un administrador activo" para que las
vistas y los formularios solo orquesten.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Usuario
from .roles import Rol

MENSAJE_ULTIMO_ADMINISTRADOR = (
    "El sistema debe conservar al menos un administrador activo."
)


def es_ultimo_administrador_activo(usuario):
    """Indica si ``usuario`` es el único administrador activo del sistema."""
    if usuario.rol != Rol.ADMINISTRADOR or not usuario.is_active:
        return False
    return not (
        Usuario.objects.filter(rol=Rol.ADMINISTRADOR, is_active=True)
        .exclude(pk=usuario.pk)
        .exists()
    )


def actualizar_usuario(usuario, *, datos_validados, actor):
    """Aplica los cambios validados conservando un administrador activo.

    ``actor`` se recibe para identificar quién realiza el cambio; la bitácora
    de auditoría está fuera del alcance de este cambio.
    """
    with transaction.atomic():
        era_ultimo_administrador = es_ultimo_administrador_activo(usuario)
        for campo, valor in datos_validados.items():
            setattr(usuario, campo, valor)

        sigue_siendo_administrador_activo = (
            usuario.rol == Rol.ADMINISTRADOR and usuario.is_active
        )
        if era_ultimo_administrador and not sigue_siendo_administrador_activo:
            raise ValidationError(MENSAJE_ULTIMO_ADMINISTRADOR)

        usuario.save()
        return usuario
