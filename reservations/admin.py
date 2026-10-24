"""Administración de solo lectura para la auditoría de reservas."""

from django.contrib import admin

from .models import HistorialReserva


@admin.register(HistorialReserva)
class HistorialReservaAdmin(admin.ModelAdmin):
    """Permite consultar el historial sin modificarlo ni borrarlo."""

    list_display = (
        "fecha_evento",
        "reserva",
        "estado_anterior",
        "estado_nuevo",
        "actor",
    )
    list_filter = ("estado_nuevo", "fecha_evento")
    search_fields = (
        "reserva__espacio__nombre",
        "reserva__motivo",
        "actor__username",
        "actor__nombre_completo",
        "observacion",
    )
    readonly_fields = tuple(
        campo.name for campo in HistorialReserva._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True
