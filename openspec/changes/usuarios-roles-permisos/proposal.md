# Proposal

## Why

El sistema ya cuenta con una base Django arrancable, pero todavía no sabe quién
actúa: no existe modelo de usuario propio, ni roles, ni autenticación utilizable, ni
control de acceso. El plan de ingeniería (2.2) ubica la autenticación y los roles
como la primera funcionalidad prioritaria porque espacios, reservas, aprobaciones e
historial dependen de identificar al solicitante, al aprobador y al administrador.

## What Changes

- Se completa el modelo de usuario personalizado `accounts.Usuario` creado por
  `base-proyecto` con `email`, nombre completo, `rol` y estado activo, mediante una
  migración nueva; `AUTH_USER_MODEL` ya apunta a ese modelo desde la migración
  inicial del proyecto.
- Se valida que el correo sea único sin distinguir mayúsculas y que la contraseña
  tenga mínimo 8 caracteres.
- Se habilita el registro público: todo usuario registrado por esa vía recibe el rol
  `SOLICITANTE` y no puede elegir otro rol.
- Se habilitan inicio y cierre de sesión con usuario y contraseña; un usuario
  inactivo no puede iniciar sesión.
- Se agrega la gestión de usuarios para el rol `ADMINISTRADOR`: listar, editar
  datos, cambiar rol y activar o desactivar cuentas.
- Se protege la invariante de "al menos un administrador activo": no se puede
  desactivar ni degradar al último `ADMINISTRADOR` activo.
- Se crea un mecanismo centralizado de restricción por rol (decorador y mixin) en
  `accounts`, reutilizable por los módulos de espacios y reservas.
- Se restringen las vistas de gestión de usuarios al `ADMINISTRADOR`: usuario
  autenticado sin permiso recibe 403 y visitante anónimo es redirigido al login.
- Se amplía `seed_data` para crear un usuario de ejemplo por rol, de forma
  idempotente, reemplazando la siembra provisional de `Group` del cambio base.
- Se actualiza la barra de navegación de `base.html` para usar rutas nombradas y
  mostrar la gestión de usuarios solo al administrador.

Fuera de alcance: recuperación de contraseña por correo, verificación de correo,
inicio de sesión con email o redes sociales, edición de perfil por el propio
usuario, creación de usuarios desde la gestión administrativa (solo edición de los
existentes), permisos granulares distintos de los tres roles y bitácora de auditoría
de cuentas.

## Capabilities

### New Capabilities

- `usuarios-roles`: identidad de las personas en el sistema (modelo de usuario
  personalizado completado con roles), registro y autenticación, roles
  `SOLICITANTE`, `APROBADOR` y `ADMINISTRADOR`, administración de cuentas y el
  mecanismo reutilizable de restricción de acceso por rol.

### Modified Capabilities

- `base-proyecto`: este cambio sustituye la siembra provisional de grupos de
  `seed_data` por usuarios de demostración y reemplaza los enlaces textuales de
  `templates/base.html` por rutas nombradas. La idempotencia de `seed_data`
  (REQ-BAS-008) y la navegación condicionada por autenticación se conservan; ambas
  modificaciones se implementan dentro de este cambio.

## Impact

- **Modelo y migraciones**: `accounts/models.py` con los campos de dominio de
  `Usuario`; migración incremental `accounts/migrations/0002_...` que depende de
  `0001_initial` de `base-proyecto`; `AUTH_USER_MODEL = "accounts.Usuario"` ya
  declarado en `config/settings.py`. No requiere reiniciar `db.sqlite3`.
- **Código de cuentas**: `accounts/roles.py`, `accounts/services.py`,
  `accounts/forms.py`, `accounts/views.py`, `accounts/urls.py`,
  `accounts/permissions.py`, `accounts/admin.py` y plantillas en
  `accounts/templates/accounts/`.
- **Configuración**: `AUTH_PASSWORD_VALIDATORS` con longitud mínima 8, `LOGIN_URL`,
  `LOGIN_REDIRECT_URL` y `LOGOUT_REDIRECT_URL` en `config/settings.py`;
  `config/urls.py` incluye `accounts.urls` (login, logout, registro y gestión).
- **Impacto cruzado**: `templates/base.html` (navegación con rutas nombradas y
  enlace de administración solo para `ADMINISTRADOR`); `core/management/commands/
  seed_data.py` (usuarios de ejemplo en vez de grupos); `core/tests/test_seed_data.py`
  (las expectativas sobre `Group` se sustituyen por usuarios).
- **Datos**: tres usuarios de demostración (`solicitante`, `aprobador`, `admin`)
  creados por `seed_data`; ninguno se duplica al repetir el comando.
- **Pruebas**: nueva suite `accounts/tests/` con pruebas de modelo, registro,
  login/logout, permisos y gestión de usuarios; los escenarios de rol y de último
  administrador se cubren con `TestCase`.
- **Dependencias**: no se agregan dependencias externas; se usan las piezas de
  autenticación incluidas en Django.
