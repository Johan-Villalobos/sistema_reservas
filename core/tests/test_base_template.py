from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from accounts.models import Usuario
from accounts.roles import Rol


class BaseTemplateTests(SimpleTestCase):
    """Comprueba la navegación condicionada por autenticación y rol."""

    def setUp(self):
        self.request = RequestFactory().get("/")

    def render(self, user):
        return render_to_string(
            "base.html",
            {"user": user},
            request=self.request,
        )

    def test_anonymous_sees_login_and_registration_links(self):
        html = self.render(AnonymousUser())

        self.assertIn('href="/accounts/login/"', html)
        self.assertIn("Iniciar sesión", html)
        self.assertIn('href="/accounts/registro/"', html)
        self.assertIn("Registrarse", html)

    def test_anonymous_does_not_see_authenticated_links(self):
        html = self.render(AnonymousUser())

        self.assertNotIn('href="/espacios/"', html)
        self.assertNotIn('href="/reservas/"', html)
        self.assertNotIn('href="/reservas/disponibilidad/"', html)
        self.assertNotIn('href="/accounts/usuarios/"', html)
        self.assertNotIn("Usuarios", html)
        self.assertNotIn("Cerrar sesión", html)

    def test_solicitante_sees_session_links_without_user_management(self):
        user = Usuario(
            username="ana",
            nombre_completo="Ana Pérez",
            rol=Rol.SOLICITANTE,
        )
        html = self.render(user)

        self.assertIn('href="/espacios/"', html)
        self.assertIn('href="/reservas/"', html)
        self.assertIn('href="/reservas/disponibilidad/"', html)
        self.assertIn("Disponibilidad", html)
        self.assertIn('action="/accounts/logout/"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn("Cerrar sesión", html)
        self.assertIn("Ana Pérez", html)
        self.assertNotIn('href="/accounts/usuarios/"', html)

    def test_administrador_sees_user_management_link(self):
        user = Usuario(
            username="admin",
            nombre_completo="Admin",
            rol=Rol.ADMINISTRADOR,
        )
        html = self.render(user)

        self.assertIn('href="/accounts/usuarios/"', html)
        self.assertIn("Usuarios", html)
        self.assertIn('action="/accounts/logout/"', html)

    def test_authenticated_user_does_not_see_anonymous_links(self):
        user = Usuario(
            username="ana",
            nombre_completo="Ana",
            rol=Rol.SOLICITANTE,
        )
        html = self.render(user)

        self.assertNotIn('href="/accounts/login/"', html)
        self.assertNotIn('href="/accounts/registro/"', html)
        self.assertNotIn("Iniciar sesión", html)
        self.assertNotIn("Registrarse", html)
