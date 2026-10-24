# Proposal

## Why

El sistema de gestión de reservas de espacios académicos necesita una base técnica
estable antes de implementar cualquier funcionalidad de negocio. Hoy el repositorio
solo contiene el plan de ingeniería y la estructura de OpenSpec: no existe proyecto
Django, ni configuración regional, ni plantilla común, ni forma de cargar datos de
ejemplo. Sin esta base, los incrementos de usuarios, espacios y reservas no pueden
construirse ni verificarse de forma reproducible.

## What Changes

- Se crea el proyecto Django monolítico con arquitectura MVT y el paquete de
  configuración `config`, junto con las cuatro aplicaciones del sistema: `core`,
  `accounts`, `spaces` y `reservations`.
- Se configura la persistencia local en SQLite (`db.sqlite3`), zona horaria
  `America/Bogota`, `USE_TZ` activado e idioma `es-co`.
- Se agrega `.gitignore` para excluir `db.sqlite3`, el entorno virtual y los
  archivos `.pyc`.
- Se versiona `requirements.txt` con las dependencias fijadas por versión.
- Se crea la plantilla `templates/base.html` con Bootstrap 5 y una barra de
  navegación que muestra enlaces distintos según el estado de autenticación, más
  la página de inicio servida por `core`.
- Se fija el usuario personalizado mínimo `accounts.Usuario` y se declara
  `AUTH_USER_MODEL = "accounts.Usuario"` antes de la primera migración, de modo que
  el proyecto nunca cree ni use la tabla `auth_user`; los campos de dominio del
  usuario llegan en el cambio `usuarios-roles-permisos`.
- Se reserva un módulo `services.py` en cada aplicación de dominio —`accounts`,
  `spaces` y `reservations`— como lugar de las reglas de negocio; en este cambio
  solo se crean los módulos con su contrato vacío.
- Se implementa el comando de administración `seed_data` con carga idempotente de
  datos de ejemplo; los grupos de rol que siembra este cambio son datos
  provisionales y los cambios posteriores pueden sustituirlos.
- Se agregan pruebas de arranque: la página de inicio responde 200, las migraciones
  se aplican sobre una base de datos vacía y el esquema usa `accounts_usuario`.

Fuera de alcance de este cambio: los campos de dominio del usuario (rol, nombre
completo y unicidad de correo), la autenticación funcional, los modelos de espacios
y reservas, las vistas de negocio y las reglas de disponibilidad o solapamiento. Se
abordan en los cambios de `accounts`, `spaces` y `reservations`.

## Capabilities

### New Capabilities

- `base-proyecto`: fundación del monolito Django (estructura MVT, configuración
  regional y de base de datos, higiene del repositorio, plantilla base con
  navegación condicionada por autenticación, comando `seed_data` idempotente y
  pruebas de arranque y de migración).

### Modified Capabilities

Ninguna. No existen especificaciones previas en `openspec/specs/`.

## Impact

- **Código nuevo**: `manage.py`, paquete `config/` (`settings.py`, `urls.py`,
  `wsgi.py`, `asgi.py`), aplicaciones `core/`, `accounts/`, `spaces/`,
  `reservations/`, `templates/base.html`, `accounts/models.py` con el usuario
  mínimo, `accounts/services.py`, `spaces/services.py`, `reservations/services.py`
  y `core/management/commands/seed_data.py`.
- **Configuración del repositorio**: `.gitignore` y `requirements.txt`.
- **Dependencias**: Django 5.x y sus dependencias transitivas, fijadas por versión;
  Bootstrap 5 servido por CDN en la plantilla base.
- **Base de datos**: `db.sqlite3` local, no versionado; migraciones iniciales del
  proyecto y de las cuatro aplicaciones, con `accounts/migrations/0001_initial.py`
  creando `accounts_usuario` y sin tabla `auth_user`.
- **Pruebas**: suite de arranque en `core/tests/` y verificación de migración en
  base limpia.
- **Restricciones para cambios posteriores**: `accounts`, `spaces` y `reservations`
  reutilizan esta estructura y sus módulos `services.py`. `usuarios-roles-permisos`
  conserva `accounts/migrations/0001_initial.py` y agrega los campos de dominio del
  usuario con una migración nueva; no debe regenerar la inicial ni exigir el
  borrado de `db.sqlite3`.
