"""Formularios de cuentas."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Usuario
from .roles import Rol
from .services import (
    MENSAJE_ULTIMO_ADMINISTRADOR,
    actualizar_usuario,
    es_ultimo_administrador_activo,
)

MENSAJE_CORREO_DUPLICADO = "Ya existe una cuenta con este correo electrónico."
MENSAJE_CUENTA_INACTIVA = "La cuenta no está activa"


def _estilizar_campos(form):
    """Agrega clases de Bootstrap a los campos del formulario."""
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-check-input")
        else:
            field.widget.attrs.setdefault("class", "form-control")


class UsuarioCreationForm(UserCreationForm):
    """Registro público: el rol no es un campo editable por el cliente."""

    class Meta:
        model = Usuario
        fields = ("username", "email", "nombre_completo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar_campos(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError(MENSAJE_CORREO_DUPLICADO)
        return email


class UsuarioAdminForm(forms.ModelForm):
    """Edición administrativa acotada a datos, rol y estado activo."""

    class Meta:
        model = Usuario
        fields = ("username", "email", "nombre_completo", "rol", "is_active")

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        _estilizar_campos(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicados = Usuario.objects.filter(email=email)
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError(MENSAJE_CORREO_DUPLICADO)
        return email

    def clean(self):
        datos = super().clean()
        rol = datos.get("rol")
        activo = datos.get("is_active")

        if (
            self.instance.pk
            and rol is not None
            and activo is not None
            and es_ultimo_administrador_activo(self.instance)
            and (rol != Rol.ADMINISTRADOR or not activo)
        ):
            raise forms.ValidationError(MENSAJE_ULTIMO_ADMINISTRADOR)

        return datos

    def save(self, commit=True):
        """Guarda a través del servicio que protege al último administrador."""
        usuario = super().save(commit=False)
        datos = {
            campo: self.cleaned_data[campo]
            for campo in self.Meta.fields
        }
        try:
            return actualizar_usuario(
                usuario,
                datos_validados=datos,
                actor=self.actor,
            )
        except DjangoValidationError as error:
            raise forms.ValidationError(error.messages)


class UsuarioAuthenticationForm(AuthenticationForm):
    """Formulario de acceso que informa cuando la cuenta está inactiva."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar_campos(self)

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            usuario = Usuario.objects.filter(username=username).first()
            if (
                usuario is not None
                and not usuario.is_active
                and usuario.check_password(password)
            ):
                raise forms.ValidationError(
                    MENSAJE_CUENTA_INACTIVA,
                    code="inactive",
                )
        return super().clean()

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                MENSAJE_CUENTA_INACTIVA,
                code="inactive",
            )
        return super().confirm_login_allowed(user)
