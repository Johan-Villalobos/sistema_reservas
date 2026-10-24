from django.test import SimpleTestCase


class HomeViewTests(SimpleTestCase):
    """Comprueba que la página de inicio responde y usa la plantilla base."""

    def test_home_responds_with_status_200(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

    def test_home_uses_base_template(self):
        response = self.client.get("/")

        nombres = [plantilla.name for plantilla in response.templates]

        self.assertIn("base.html", nombres)
        self.assertIn("core/home.html", nombres)

    def test_home_shows_system_name(self):
        response = self.client.get("/")

        self.assertContains(
            response,
            "Gestión de Reservas de Espacios Académicos",
        )
