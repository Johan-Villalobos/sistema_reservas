"""Rutas de la aplicación reservations."""

from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("", views.SolicitudListView.as_view(), name="solicitud_lista"),
    path(
        "nueva/",
        views.SolicitudCreateView.as_view(),
        name="solicitud_crear",
    ),
    path(
        "disponibilidad/",
        views.DisponibilidadView.as_view(),
        name="disponibilidad",
    ),
    path(
        "<int:pk>/",
        views.SolicitudDetailView.as_view(),
        name="solicitud_detalle",
    ),
]
