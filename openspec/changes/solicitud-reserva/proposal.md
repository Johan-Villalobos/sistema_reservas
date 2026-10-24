# Proposal

## Why

Con usuarios, roles y un catálogo de espacios ya definidos, el sistema todavía no
permite el acto central del negocio: solicitar un espacio en una fecha y franja
horaria. Sin solicitudes no hay nada que aprobar, rechazar, cancelar ni auditar. El
plan de ingeniería (2.2) ubica la creación de solicitudes como la tercera
funcionalidad prioritaria y la base para el control de disponibilidad.

## What Changes

- Se crea el modelo `Reserva` en la aplicación `reservations`, con espacio,
  solicitante, fecha, hora de inicio, hora de fin, motivo, estado y fecha de
  creación, más la restricción de base de datos `hora_fin > hora_inicio`.
- Toda solicitud nueva queda en estado `PENDIENTE` y registra al solicitante
  autenticado y su fecha de creación; el cliente no puede imponer estado ni
  solicitante.
- Se valida que la franja esté contenida en un solo día, que la hora de fin sea
  mayor que la de inicio y que la fecha y hora de inicio no estén en el pasado.
- Se rechazan solicitudes sobre espacios inactivos y fuera del horario operativo
  configurable en `settings` (valor inicial 06:00 a 22:00).
- Se exige un motivo obligatorio de máximo 255 caracteres.
- Todo usuario autenticado y activo, sin importar su rol (`SOLICITANTE`,
  `APROBADOR` o `ADMINISTRADOR`), puede crear solicitudes; el rol restringe aprobar y
  administrar, no solicitar.
- Todo usuario autenticado puede listar sus propias solicitudes y abrir su detalle.
- El detalle es visible solo para el solicitante, los `APROBADOR` y los
  `ADMINISTRADOR`; cualquier otro usuario autenticado recibe 403 y un anónimo es
  redirigido al login.
- Las reglas de creación se concentran en `reservations/services.py`, dejando las
  vistas como orquestadoras, conforme a REQ-BAS-007.
- `Reserva.estado` solo se modifica mediante servicios; las vistas y formularios no lo
  asignan directamente. Se documenta que SQLite no impide una escritura directa por
  ORM y que esa vía no está soportada.

Fuera de alcance y dependencia explícita: este cambio **no** valida cruces ni
solapamientos con otras reservas, no implementa la consulta de disponibilidad, no
cambia estados ni permite aprobar, rechazar o cancelar, no lista solicitudes ajenas
para aprobadores y no carga reservas de ejemplo en `seed_data`. La detección de
conflictos pertenece a la capacidad `disponibilidad`, que deberá reutilizar y
extender el servicio de creación.

## Capabilities

### New Capabilities

- `solicitud-reserva`: creación de solicitudes de reserva por usuarios autenticados y
  activos de cualquier rol, con sus validaciones de franja, fecha, espacio, motivo y
  horario operativo; estado inicial `PENDIENTE`; regla de que las transiciones de
  estado pasan solo por servicios; listado de solicitudes propias y detalle con
  visibilidad restringida al solicitante, aprobadores y administradores.

### Modified Capabilities

Ninguna. `base-proyecto`, `usuarios-roles` y `espacios` mantienen sus requisitos: se
consumen sus modelos, roles, mecanismo de permisos y catálogo sin cambiarlos. El
enlace de navegación "Reservas" de la plantilla base ya está previsto para usuarios
autenticados y solo se materializa con la ruta nombrada de este cambio.

## Impact

- **Modelo y migración**: `reservations/models.py` con `Reserva` y
  `EstadoReserva`; `reservations/migrations/0001_initial.py` con clave foránea a
  `spaces.EspacioAcademico` (`PROTECT`), clave foránea a `settings.AUTH_USER_MODEL`
  (`PROTECT`), `CheckConstraint` de horas y campos de auditoría básicos.
- **Reglas de negocio**: `reservations/services.py` con la validación y la creación
  transaccional; es el punto que `disponibilidad` extenderá con la detección de
  solapamientos y el único lugar donde se escribe `estado`. SQLite no impide una
  escritura directa por ORM; se documenta como vía no soportada (REQ-SOL-011).
- **Formulario, vistas y rutas**: `reservations/forms.py`, `reservations/views.py`,
  `reservations/urls.py` y `reservations/permissions.py` con las rutas
  `reservations:solicitud_lista`, `reservations:solicitud_crear` y
  `reservations:solicitud_detalle`.
- **Plantillas**: `reservations/templates/reservations/solicitud_lista.html`,
  `solicitud_form.html` y `solicitud_detalle.html`; actualización del enlace
  "Reservas" en `templates/base.html` con `{% url %}`.
- **Configuración**: `HORARIO_OPERATIVO_INICIO = "06:00"` y
  `HORARIO_OPERATIVO_FIN = "22:00"` en `config/settings.py`, con lectura centralizada
  en el servicio.
- **Pruebas**: nueva suite `reservations/tests/` para modelo, formulario, servicio,
  vistas y permisos de detalle.
- **Dependencias externas**: ninguna nueva.
- **Dependencias internas**: requiere `base-proyecto`, `usuarios-roles-permisos` y
  `gestion-espacios` implementados.
