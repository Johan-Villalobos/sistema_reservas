"""Vistas de la aplicación core."""

from django.shortcuts import render


def home(request):
    """Renderiza la página de inicio del sistema."""
    return render(request, "core/home.html")
