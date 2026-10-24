"""Rutas de la aplicación spaces."""

from django.urls import path

from . import views

app_name = "spaces"

urlpatterns = [
    path("", views.EspacioListView.as_view(), name="espacio_lista"),
    path("crear/", views.EspacioCreateView.as_view(), name="espacio_crear"),
    path("<int:pk>/", views.EspacioDetailView.as_view(), name="espacio_detalle"),
    path(
        "<int:pk>/editar/",
        views.EspacioUpdateView.as_view(),
        name="espacio_editar",
    ),
    path(
        "<int:pk>/desactivar/",
        views.EspacioDesactivarView.as_view(),
        name="espacio_desactivar",
    ),
]
