"""Vistas del catálogo de espacios académicos."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.permissions import RolRequeridoMixin
from accounts.roles import Rol

from .choices import TipoEspacio
from .forms import EspacioForm
from .models import EspacioAcademico
from .services import actualizar_espacio, crear_espacio, desactivar_espacio


class EspacioListView(LoginRequiredMixin, ListView):
    """Catálogo de espacios activos, con todos los estados para el admin."""

    model = EspacioAcademico
    template_name = "spaces/espacio_lista.html"
    context_object_name = "espacios"

    def get_queryset(self):
        if self.request.user.es_administrador:
            espacios = EspacioAcademico.objects.all()
        else:
            espacios = EspacioAcademico.objects.activos()

        tipo = self.request.GET.get("tipo")
        if tipo in TipoEspacio.values:
            espacios = espacios.filter(tipo=tipo)
        return espacios

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        tipo = self.request.GET.get("tipo")
        contexto["tipos"] = TipoEspacio.choices
        contexto["tipo_seleccionado"] = tipo if tipo in TipoEspacio.values else ""
        contexto["tipo_invalido"] = bool(tipo) and tipo not in TipoEspacio.values
        contexto["puede_administrar"] = self.request.user.es_administrador
        return contexto


class EspacioDetailView(LoginRequiredMixin, DetailView):
    """Detalle visible para autenticados; inactivos solo para el admin."""

    model = EspacioAcademico
    template_name = "spaces/espacio_detalle.html"
    context_object_name = "espacio"

    def get_queryset(self):
        if self.request.user.es_administrador:
            return EspacioAcademico.objects.all()
        return EspacioAcademico.objects.activos()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["puede_administrar"] = self.request.user.es_administrador
        return contexto


class EspacioCreateView(RolRequeridoMixin, CreateView):
    """Creación de espacios exclusiva del administrador."""

    model = EspacioAcademico
    form_class = EspacioForm
    template_name = "spaces/espacio_form.html"
    roles_permitidos = [Rol.ADMINISTRADOR]

    def form_valid(self, form):
        try:
            self.object = crear_espacio(**form.cleaned_data)
        except DjangoValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            "El espacio se creó correctamente.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("spaces:espacio_detalle", kwargs={"pk": self.object.pk})


class EspacioUpdateView(RolRequeridoMixin, UpdateView):
    """Edición de datos del espacio exclusiva del administrador."""

    model = EspacioAcademico
    form_class = EspacioForm
    template_name = "spaces/espacio_form.html"
    context_object_name = "espacio"
    roles_permitidos = [Rol.ADMINISTRADOR]

    def form_valid(self, form):
        try:
            self.object = actualizar_espacio(
                self.object,
                datos_validados=form.cleaned_data,
            )
        except DjangoValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            "Los datos del espacio se actualizaron correctamente.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("spaces:espacio_detalle", kwargs={"pk": self.object.pk})


class EspacioDesactivarView(RolRequeridoMixin, View):
    """Desactivación lógica; solo acepta POST y es idempotente."""

    roles_permitidos = [Rol.ADMINISTRADOR]
    http_method_names = ["post"]

    def post(self, request, pk):
        espacio = get_object_or_404(EspacioAcademico, pk=pk)
        desactivar_espacio(espacio)
        messages.success(
            request,
            f"El espacio «{espacio.nombre}» quedó desactivado.",
        )
        return redirect("spaces:espacio_lista")
