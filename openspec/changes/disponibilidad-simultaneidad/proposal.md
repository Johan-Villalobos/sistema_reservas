# Proposal

## Why

Hoy es posible crear solicitudes y aprobarlas sin que el sistema detecte que dos
reservas del mismo espacio se pisan. Ese es el problema central del plan (2.6) y el
riesgo R1: reservas simultáneas o solapadas que la institución descubre el mismo día
de uso. Sin una validación de cruces compartida por la creación y la aprobación, el
catálogo de espacios no evita duplicidades aunque el resto del flujo funcione.

## What Changes

- Se define la regla de cruce del plan 2.6: dos reservas del mismo espacio y fecha se
  cruzan cuando `inicio_A < fin_B` y `fin_A > inicio_B`.
- Solo las reservas `APROBADA` bloquean el espacio; `PENDIENTE`, `RECHAZADA` y
  `CANCELADA` no lo bloquean.
- La creación de una solicitud se rechaza con un mensaje claro si se cruza con una
  reserva aprobada del mismo espacio y fecha.
- Las reservas contiguas (una termina cuando empieza la otra) se permiten; también
  las del mismo horario en otro espacio u otra fecha.
- La aprobación de una solicitud revalida el cruce dentro de una transacción atómica
  y se impide si existe conflicto, incluyendo el caso de dos solicitudes `PENDIENTE`
  que se cruzan: la segunda no puede aprobarse mientras la primera siga aprobada.
- Se agrega la consulta de disponibilidad de un espacio para una fecha, mostrando
  únicamente las franjas ocupadas por reservas aprobadas y recalculándolas en cada
  petición.
- La validación de cruces se implementa en una sola función de servicio reutilizada
  por la creación y la aprobación, ampliando `reservations/services.py`.

Fuera de alcance: la interfaz de aprobación y rechazo, la cancelación, el historial
de estados (`HistorialReserva`), el cálculo de franjas libres o sugerencias de
horario, la visualización tipo calendario, la edición de solicitudes, la reserva
recurrente y el bloqueo de espacios por mantenimiento. Este cambio expone la
aprobación mínima a nivel de servicio porque REQ-DIS-006 y REQ-DIS-007 la exigen; la
interfaz y el flujo completo de decisión pertenecen a la capacidad `aprobacion`.

## Capabilities

### New Capabilities

- `disponibilidad`: regla única de detección de cruces por espacio y fecha,
  comportamiento de los estados frente al bloqueo, prevención de conflictos al crear
  y al aprobar dentro de transacción, y consulta de franjas ocupadas por reservas
  aprobadas.

### Modified Capabilities

- `solicitud-reserva`: este cambio extiende `crear_solicitud` con la validación de
  disponibilidad y agrega `aprobar_reserva` en `reservations/services.py`. La creación
  conserva sus requisitos y el modelo `Reserva` no cambia; la transición mínima
  `PENDIENTE → APROBADA` existe para verificar REQ-DIS-006 y REQ-DIS-007 y la completa
  `aprobacion-rechazo`.
- `cancelacion-historial` (cambio posterior): recibe el escenario de liberación de la
  franja cuando una reserva deja de estar `APROBADA`; este cambio no define esa
  transición.

## Impact

- **Servicio**: `reservations/services.py` incorpora `validar_disponibilidad`,
  la integración en `crear_solicitud` y `aprobar_reserva` con revalidación
  transaccional; `reservations/permissions.py` no cambia.
- **Consultas**: nueva función de franjas ocupadas y vista de disponibilidad con
  ruta `reservations:disponibilidad`.
- **Vistas y plantillas**: `DisponibilidadView` o vista equivalente, formulario de
  consulta por espacio y fecha, y
  `reservations/templates/reservations/disponibilidad.html`; enlaces desde el
  listado de reservas y la barra de navegación.
- **Sin migraciones**: no se agregan modelos ni campos; se reutilizan `Reserva`,
  `EspacioAcademico` y los estados existentes.
- **Pruebas**: nueva suite de disponibilidad con la matriz completa de cruces,
  límites de contigüidad, estados que no bloquean, aprobación de solicitudes que se
  cruzan, reintento tras conflicto y consulta de franjas.
- **Dependencias internas**: requiere `solicitud-reserva` implementado (modelo
  `Reserva`, estados y `crear_solicitud`) y, por transitividad, los tres cambios
  anteriores.
- **Dependencias externas**: ninguna nueva.
