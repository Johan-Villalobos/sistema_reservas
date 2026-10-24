# Proposal

## Why

El sistema ya define quién puede actuar (usuarios y roles), pero todavía no existe
el recurso sobre el que se reserva: los espacios académicos. Sin un catálogo
centralizado de laboratorios, auditorios y salas de cómputo, con su capacidad,
ubicación y estado, no es posible consultar disponibilidad ni crear solicitudes de
reserva. El plan de ingeniería (2.2) ubica la gestión de espacios como la segunda
funcionalidad prioritaria, inmediatamente después de la autenticación.

## What Changes

- Se crea el modelo `EspacioAcademico` en la aplicación `spaces` con nombre, tipo,
  capacidad, ubicación, descripción y estado activo.
- Se restringe el tipo a `LABORATORIO`, `AUDITORIO` o `SALA_COMPUTO`.
- Se garantiza que el nombre sea único sin distinguir mayúsculas y que la capacidad
  sea un entero mayor que cero, con validación en formulario y restricciones en base
  de datos.
- Se habilita la creación, edición y desactivación de espacios solo para el rol
  `ADMINISTRADOR`, reutilizando el mecanismo centralizado de `accounts`.
- La desactivación es lógica: el registro permanece en la base de datos con
  `activo = False` y no se ofrece eliminación física.
- Se habilita el listado de espacios activos para todo usuario autenticado, con
  filtro por tipo; el `ADMINISTRADOR` ve además los inactivos.
- Se agrega la vista de detalle de un espacio para usuarios autenticados.
- Se implementan las reglas de normalización, unicidad y capacidad en
  `spaces/services.py`, de modo que formularios, vistas y `seed_data` compartan la
  misma validación y las vistas solo orquesten.
- Se amplía `seed_data` con espacios de ejemplo, uno por tipo, de forma idempotente.
- Se actualiza la navegación de `base.html` para enlazar el catálogo de espacios con
  la ruta nombrada correspondiente.

Fuera de alcance: consulta de disponibilidad por franjas, calendario, imágenes o
equipamiento de los espacios, reactivación de espacios desactivados, eliminación
física, paginación del listado, importación masiva y cualquier reserva asociada
(corresponden al cambio de `reservas`).

## Capabilities

### New Capabilities

- `espacios`: catálogo de espacios académicos, con su clasificación, capacidad,
  ubicación, estado lógico, reglas de unicidad y validación, consulta filtrada por
  tipo para usuarios autenticados y administración exclusiva por el rol
  `ADMINISTRADOR`.

### Modified Capabilities

- `base-proyecto`: este cambio amplía `seed_data` con espacios de ejemplo y
  reemplaza el enlace textual de espacios de `templates/base.html` por una ruta
  nombrada. La idempotencia de `seed_data` (REQ-BAS-008) y la navegación
  condicionada por autenticación se conservan; la prueba de la siembra de espacios
  se ubica en `spaces/tests/`, mientras `core` conserva solo la de usuarios.

## Impact

- **Modelo y migración**: `spaces/models.py` con `EspacioAcademico` y
  `spaces/migrations/0001_initial.py`, incluyendo restricciones de unicidad
  insensible a mayúsculas y de capacidad positiva.
- **Código de espacios**: `spaces/services.py`, `spaces/forms.py`, `spaces/views.py`,
  `spaces/urls.py`, `spaces/templates/spaces/` y `spaces/tests/`.
- **Dependencias internas**: importa `Rol` y el mecanismo `roles_requeridos` /
  `RolRequeridoMixin` de `accounts`, y usa `settings.AUTH_USER_MODEL` solo para
  autenticación; no agrega claves foráneas a usuarios en este cambio.
- **Plantilla base**: enlace "Espacios" con `{% url 'spaces:espacio_lista' %}`
  visible para usuarios autenticados.
- **Datos de ejemplo**: `core/management/commands/seed_data.py` incorpora un
  laboratorio, un auditorio y una sala de cómputo con nombres y capacidades fijos;
  repetir el comando no duplica registros. La comprobación de los espacios se agrega
  en `spaces/tests/test_seed_data.py`; `core/tests/test_seed_data.py` conserva solo
  las comprobaciones de usuarios.
- **Pruebas**: nueva suite `spaces/tests/` para modelo, formularios, vistas,
  permisos, filtro y desactivación lógica; se conserva la prueba de reutilización
  del mecanismo de permisos creada por `usuarios-roles-permisos`.
- **Dependencias externas**: ninguna nueva.
