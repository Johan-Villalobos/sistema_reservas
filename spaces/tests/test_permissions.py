"""Reutilización del mecanismo de roles de accounts fuera de accounts."""

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path
from django.views import View

from accounts.models import Usuario
from accounts.permissions import RolRequeridoMixin, roles_requeridos
from accounts.roles import Rol


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
class ReutilizacionPermisosSpacesTests(TestCase):
    """El mecanismo de accounts se comporta igual desde spaces."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            username="admin_spaces",
            email="admin_spaces@ejemplo.com",
            password="ClaveSegura123!",
            nombre_completo="Admin Spaces",
            rol=Rol.ADMINISTRADOR,
        )
        cls.solicitante = Usuario.objects.create_user(
            username="solicitante_spaces",
            email="solicitante_spaces@ejemplo.com",
            password="ClaveSegura123!",
            nombre_completo="Solicitante Spaces",
            rol=Rol.SOLICITANTE,
        )

    def test_req_usr_009_reutilizacion_decorador_permite_al_rol_autorizado(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 200)

    def test_req_usr_009_reutilizacion_decorador_devuelve_403_al_autenticado_sin_rol(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 403)

    def test_req_usr_009_reutilizacion_decorador_redirige_al_anonimo_con_next(self):
        respuesta = self.client.get("/funcion/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            "/accounts/login/?next=/funcion/",
        )

    def test_req_usr_009_reutilizacion_mixin_permite_al_rol_autorizado(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 200)

    def test_req_usr_009_reutilizacion_mixin_devuelve_403_al_autenticado_sin_rol(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 403)

    def test_req_usr_009_reutilizacion_mixin_redirige_al_anonimo_con_next(self):
        respuesta = self.client.get("/clase/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            "/accounts/login/?next=/clase/",
        )
