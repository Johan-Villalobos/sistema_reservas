"""Vistas de cuentas."""

from django import forms
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (
    UsuarioAdminForm,
    UsuarioAuthenticationForm,
    UsuarioCreationForm,
)
from .models import Usuario
from .permissions import RolRequeridoMixin
from .roles import Rol


class RegistroView(CreateView):
    """Registro público; el rol se fija en el servidor."""

    form_class = UsuarioCreationForm
    template_name = "accounts/registro.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        form.instance.rol = Rol.SOLICITANTE
        respuesta = super().form_valid(form)
        messages.success(
            self.request,
            "La cuenta se creó correctamente. Ya puedes iniciar sesión.",
        )
        return respuesta


class UsuarioLoginView(LoginView):
    """Inicio de sesión con el formulario que informa cuentas inactivas."""

    authentication_form = UsuarioAuthenticationForm
    template_name = "accounts/login.html"
    next_page = reverse_lazy("core:home")


class UsuarioLogoutView(LogoutView):
    """Cierre de sesión (solo POST)."""

    next_page = reverse_lazy("core:home")


class UsuarioListView(RolRequeridoMixin, ListView):
    """Listado de usuarios para el administrador."""

    model = Usuario
    template_name = "accounts/usuario_lista.html"
    context_object_name = "usuarios"
    roles_permitidos = [Rol.ADMINISTRADOR]

    def get_queryset(self):
        return Usuario.objects.order_by("username")


class UsuarioUpdateView(RolRequeridoMixin, UpdateView):
    """Edición de datos, rol y estado de una cuenta."""

    model = Usuario
    form_class = UsuarioAdminForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario_lista")
    roles_permitidos = [Rol.ADMINISTRADOR]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            self.object = form.save()
        except forms.ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            "Los datos del usuario se actualizaron correctamente.",
        )
        return HttpResponseRedirect(self.get_success_url())
