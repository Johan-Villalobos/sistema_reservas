"""Utilidades compartidas por las pruebas de cuentas."""

from uuid import uuid4

from accounts.models import Usuario
from accounts.roles import Rol

CONTRASENA_PRUEBA = "ClaveSegura123!"


def crear_usuario(rol=Rol.SOLICITANTE, activo=True, **datos):
    """Crea un usuario de prueba con valores únicos por defecto.

    ``rol`` y ``activo`` son parámetros explícitos para que cada prueba declare
    el escenario que necesita; el resto de campos puede sobrescribirse con
    ``**datos``.
    """
    sufijo = uuid4().hex[:8]
    datos.setdefault("username", f"usuario_{sufijo}")
    datos.setdefault("email", f"{datos['username']}@ejemplo.com")
    datos.setdefault("nombre_completo", "Usuario de Prueba")
    password = datos.pop("password", CONTRASENA_PRUEBA)

    return Usuario.objects.create_user(
        password=password,
        rol=rol,
        is_active=activo,
        **datos,
    )
