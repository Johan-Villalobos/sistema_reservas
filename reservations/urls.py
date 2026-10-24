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
        "pendientes/",
        views.ReservaPendienteListView.as_view(),
        name="pendientes",
    ),
    path(
        "historial/",
        views.HistorialReservaListView.as_view(),
        name="historial",
    ),
    path(
        "<int:pk>/aprobar/",
        views.AprobarReservaView.as_view(),
        name="aprobar",
    ),
    path(
        "<int:pk>/rechazar/",
        views.RechazarReservaView.as_view(),
        name="rechazar",
    ),
    path(
        "<int:pk>/cancelar/",
        views.CancelarReservaView.as_view(),
        name="cancelar",
    ),
    path(
        "<int:pk>/",
        views.SolicitudDetailView.as_view(),
        name="solicitud_detalle",
    ),
]
