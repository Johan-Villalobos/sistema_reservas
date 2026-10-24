"""Formulario del catálogo de espacios académicos."""

from django import forms

from .choices import TipoEspacio
from .models import EspacioAcademico
from .services import MENSAJE_NOMBRE_DUPLICADO, normalizar_nombre

MENSAJE_CAPACIDAD_INVALIDA = (
    "La capacidad debe ser un número entero mayor que cero."
)


class EspacioForm(forms.ModelForm):
    """Creación y edición de un espacio; ``activo`` no es editable aquí."""

    class Meta:
        model = EspacioAcademico
        fields = ("nombre", "tipo", "capacidad", "ubicacion", "descripcion")
        labels = {
            "nombre": "Nombre",
            "tipo": "Tipo",
            "capacidad": "Capacidad",
            "ubicacion": "Ubicación",
            "descripcion": "Descripción",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "capacidad": forms.NumberInput(attrs={"class": "form-control"}),
            "ubicacion": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data["nombre"])
        duplicados = EspacioAcademico.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError(MENSAJE_NOMBRE_DUPLICADO)
        return nombre

    def clean_capacidad(self):
        capacidad = self.cleaned_data["capacidad"]
        if capacidad is None or capacidad < 1:
            raise forms.ValidationError(MENSAJE_CAPACIDAD_INVALIDA)
        return capacidad
