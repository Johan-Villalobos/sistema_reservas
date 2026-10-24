"""Mecanismo centralizado de restricción de acceso por rol.

Contrato
========

``roles_requeridos(*roles)`` (vistas basadas en función) y
``RolRequeridoMixin`` (vistas basadas en clase) aplican la misma política, en
este orden:

1. Si la petición es de un visitante anónimo, se redirige a
   ``settings.LOGIN_URL`` incluyendo la ruta original en el parámetro ``next``.
2. Si el usuario está autenticado pero su ``rol`` no está entre los roles
   autorizados, se lanza ``PermissionDenied`` y la respuesta es 403.
3. Si el rol está autorizado, la vista se ejecuta normalmente.

``spaces`` y ``reservations`` deben importar este módulo en lugar de repetir la
comprobación: ``roles_requeridos(Rol.APROBADOR)`` o
``class MiVista(RolRequeridoMixin, View): roles_permitidos = [Rol.APROBADOR]``.
"""

from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def usuario_tiene_rol(usuario, roles):
    """Comprueba que ``usuario`` esté autenticado y tenga uno de los roles."""
    return bool(usuario.is_authenticated and usuario.rol in set(roles))


def roles_requeridos(*roles):
    """Restringe una vista de función a los roles indicados."""

    def decorador(vista):
        @wraps(vista)
        def vista_protegida(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not usuario_tiene_rol(request.user, roles):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return vista_protegida

    return decorador


class RolRequeridoMixin(AccessMixin):
    """Restringe una vista basada en clase a ``roles_permitidos``."""

    roles_permitidos = ()
    raise_exception = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not usuario_tiene_rol(request.user, self.roles_permitidos):
            raise PermissionDenied(self.get_permission_denied_message())
        return super().dispatch(request, *args, **kwargs)
