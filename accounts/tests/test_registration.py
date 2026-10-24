"""Pruebas del registro público.

Cubre REQ-USR-002 y REQ-USR-003.
"""

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import Usuario
from accounts.roles import Rol
from accounts.tests.utils import CONTRASENA_PRUEBA, crear_usuario


class RegistroTests(TestCase):
    """Registro público: rol fijado en el servidor y validaciones."""

    def datos_registro(self, **cambios):
        datos = {
            "username": "nueva_persona",
            "email": "nueva_persona@ejemplo.com",
            "nombre_completo": "Nueva Persona",
            "password1": CONTRASENA_PRUEBA,
            "password2": CONTRASENA_PRUEBA,
        }
        datos.update(cambios)
        return datos

    def test_req_usr_003_registro_exitoso_asigna_solicitante(self):
        respuesta = self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(),
        )

        self.assertRedirects(respuesta, reverse("accounts:login"))
        usuario = Usuario.objects.get(username="nueva_persona")
        self.assertEqual(usuario.rol, Rol.SOLICITANTE)

    def test_req_usr_003_registro_exitoso_muestra_mensaje_de_exito(self):
        respuesta = self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(),
            follow=True,
        )

        mensajes = [str(mensaje) for mensaje in get_messages(respuesta.wsgi_request)]
        self.assertTrue(
            any("se creó correctamente" in mensaje for mensaje in mensajes)
        )

    def test_req_usr_003_el_rol_enviado_por_el_cliente_se_ignora(self):
        self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(rol=Rol.ADMINISTRADOR),
        )

        usuario = Usuario.objects.get(username="nueva_persona")
        self.assertEqual(usuario.rol, Rol.SOLICITANTE)

    def test_req_usr_002_registro_con_correo_repetido_falla(self):
        crear_usuario(email="ana@ejemplo.com")

        respuesta = self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(email="Ana@Ejemplo.com"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("email", respuesta.context["form"].errors)
        self.assertFalse(
            Usuario.objects.filter(username="nueva_persona").exists()
        )

    def test_req_usr_002_registro_con_contrasena_de_siete_caracteres_falla(self):
        respuesta = self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(password1="Ab1!xyz", password2="Ab1!xyz"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password2", respuesta.context["form"].errors)
        self.assertFalse(
            Usuario.objects.filter(username="nueva_persona").exists()
        )

    def test_req_usr_002_registro_con_contrasena_de_ocho_caracteres_se_acepta(self):
        respuesta = self.client.post(
            reverse("accounts:registro"),
            self.datos_registro(password1="Abcd123!", password2="Abcd123!"),
        )

        self.assertRedirects(respuesta, reverse("accounts:login"))
        self.assertTrue(
            Usuario.objects.filter(username="nueva_persona").exists()
        )
