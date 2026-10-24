"""Rutas de la aplicación accounts."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.UsuarioLoginView.as_view(), name="login"),
    path("logout/", views.UsuarioLogoutView.as_view(), name="logout"),
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path(
        "usuarios/<int:pk>/editar/",
        views.UsuarioUpdateView.as_view(),
        name="usuario_editar",
    ),
]
