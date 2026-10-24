"""Pruebas del mecanismo centralizado de restricción por rol.

Cubre REQ-USR-009 con el decorador y el mixin definidos en ``accounts``.
"""

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path
from django.views import View

from accounts.permissions import RolRequeridoMixin, roles_requeridos
from accounts.roles import Rol
from accounts.tests.utils import crear_usuario


@roles_requeridos(Rol.ADMINISTRADOR)
def vista_funcion_protegida(request):
    return HttpResponse("vista de función permitida")


class VistaClaseProtegida(RolRequeridoMixin, View):
    roles_permitidos = [Rol.ADMINISTRADOR]

    def get(self, request):
        return HttpResponse("vista de clase permitida")


urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("espacios/", include("spaces.urls")),
    path("reservas/", include("reservations.urls")),
    path("", include("core.urls")),
    path("funcion/", vista_funcion_protegida, name="funcion_protegida"),
    path("clase/", VistaClaseProtegida.as_view(), name="clase_protegida"),
]


@override_settings(ROOT_URLCONF=__name__)
class PermisosTests(TestCase):
    """Contrato del decorador y del mixin para cada tipo de usuario."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = crear_usuario(username="admin", rol=Rol.ADMINISTRADOR)
        cls.solicitante = crear_usuario(
            username="solicitante",
            rol=Rol.SOLICITANTE,
        )

    def test_req_usr_009_decorador_permite_al_rol_autorizado(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "vista de función permitida")

    def test_req_usr_009_decorador_rechaza_rol_no_autorizado_con_403(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 403)

    def test_req_usr_009_decorador_redirige_al_anonimo_al_login(self):
        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], "/accounts/login/?next=/funcion/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_req_usr_009_mixin_permite_al_rol_autorizado(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "vista de clase permitida")

    def test_req_usr_009_mixin_rechaza_rol_no_autorizado_con_403(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 403)

    def test_req_usr_009_mixin_redirige_al_anonimo_al_login(self):
        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], "/accounts/login/?next=/clase/")
        self.assertNotIn("_auth_user_id", self.client.session)
