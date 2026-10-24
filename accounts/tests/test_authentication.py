"""Pruebas de inicio y cierre de sesión.

Cubre REQ-USR-004 y REQ-USR-005.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.tests.utils import CONTRASENA_PRUEBA, crear_usuario


class AutenticacionTests(TestCase):
    """Login correcto, credenciales inválidas, inactivo y logout por POST."""

    def test_req_usr_004_login_correcto_redirige_al_inicio_y_autentica(self):
        usuario = crear_usuario(username="ana")

        respuesta = self.client.post(
            reverse("accounts:login"),
            {"username": "ana", "password": CONTRASENA_PRUEBA},
        )

        self.assertRedirects(respuesta, reverse("core:home"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            usuario.pk,
        )

    def test_req_usr_004_credenciales_invalidas_muestran_error_sin_autenticar(self):
        crear_usuario(username="ana")

        respuesta = self.client.post(
            reverse("accounts:login"),
            {"username": "ana", "password": "ClaveIncorrecta123!"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_req_usr_004_logout_por_post_cierra_la_sesion(self):
        usuario = crear_usuario(username="ana")
        self.client.force_login(usuario)

        respuesta = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(respuesta, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_req_usr_005_usuario_inactivo_no_entra(self):
        crear_usuario(username="inactivo", activo=False)

        respuesta = self.client.post(
            reverse("accounts:login"),
            {"username": "inactivo", "password": CONTRASENA_PRUEBA},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La cuenta no está activa")
        self.assertNotIn("_auth_user_id", self.client.session)
