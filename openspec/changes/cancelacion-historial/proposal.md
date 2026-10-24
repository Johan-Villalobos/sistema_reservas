# Proposal

## Why

El ciclo de vida de una reserva todavía no puede cerrarse: una solicitud
`PENDIENTE` o `APROBADA` no se puede cancelar, de modo que una reserva aprobada
bloquea el espacio indefinidamente aunque el solicitante ya no la necesite. Además,
solo se conserva la última decisión en la propia reserva, sin un rastro auditable de
quién cambió el estado, cuándo y con qué observación. Este cambio completa las
transiciones del plan 2.5 y agrega la trazabilidad exigida por el plan 2.4.

## What Changes

- Se crea el modelo `HistorialReserva` con reserva, estado anterior, estado nuevo,
  actor, fecha del evento y observación, junto con su migración.
- Se implementa el servicio `cancelar_reserva`, que permite al solicitante cancelar
  sus propias reservas y al `ADMINISTRADOR` cancelar cualquiera, solo en estado
  `PENDIENTE` o `APROBADA` y solo antes de la hora de inicio.
- Se impide cancelar reservas `RECHAZADA` o `CANCELADA`, reservas ya iniciadas y
  reservas de otro usuario; la violación de propiedad responde 403.
- Al cancelar una reserva `APROBADA`, el espacio deja de estar ocupado para esa
  franja, porque solo las reservas `APROBADA` bloquean la disponibilidad.
- La cancelación conserva `fecha_decision`: solo cambia el estado y la fecha de
  actualización, de modo que el instante real de la aprobación o del rechazo no se
  pierde.
- Todas las transiciones de estado pasan por `reservations/services.py`; las vistas no
  asignan `estado`. SQLite no impide una escritura directa por ORM, que se documenta
  como vía no soportada.
- Cada transición de estado (creación, aprobación, rechazo y cancelación) registra un
  evento de historial dentro de la misma transacción atómica que el cambio de estado.
  Si el historial no se puede guardar, el estado no cambia.
- Los registros de historial son inmutables desde la aplicación: no se editan ni se
  eliminan por modelo, por queryset ni desde la administración.
- Se agrega un listado de historial con alcance por usuario y filtros por estado
  resultante, fecha del evento y espacio; el solicitante ve solo sus reservas y el
  `ADMINISTRADOR` ve todas.
- Se agrega una vista de confirmación de cancelación y una sección de historial en el
  detalle de la reserva, visible solo para el solicitante y los administradores.

Fuera de alcance: exigir un motivo de cancelación, editar o reactivar reservas,
restaurar reservas canceladas, notificar por correo, paginar el historial, exportar
auditoría, implementar disparadores de base de datos para inmutabilidad y gestionar
el historial desde el admin de Django más allá de una consulta de solo lectura.

## Capabilities

### New Capabilities

- `cancelacion-historial`: cancelación de reservas propias o de cualquier reserva
  por un administrador, con reglas de estado y de tiempo; liberación del espacio al
  cancelar una reserva aprobada; registro atómico e inmutable de cada transición de
  estado; y consulta del historial con alcance por usuario y filtros.

### Modified Capabilities

- `solicitud-reserva`: `REQ-SOL-011` exige que `Reserva.estado` cambie solo mediante
  servicios. Este cambio agrega `cancelar_reserva` como la vía soportada a
  `CANCELADA` y mantiene la regla; también se apoya en `crear_solicitud`, que ya la
  cumple. El contrato del modelo no cambia salvo el nuevo `HistorialReserva`.
- `aprobacion-rechazo`: el diseño de ese cambio dejó la cancelación y
  `HistorialReserva` para este incremento y registró `fecha_decision` como campo
  propio. Aquí se agregan las transiciones `PENDIENTE → CANCELADA` y
  `APROBADA → CANCELADA` y se garantiza que la cancelación no sobrescribe
  `fecha_decision`; la aprobación y el rechazo conservan su comportamiento.



## Impact

- **Modelo y migración**: `reservations/models.py` con `HistorialReserva` y su
  `Meta`; `reservations/migrations/0003_historialreserva.py`, posterior a la migración
  `0002` de `aprobacion-rechazo`.
- **Servicios**: `reservations/services.py` con `cancelar_reserva`,
  `reserva_es_cancelable` y el registro compartido de historial; se amplían
  `crear_solicitud` y `_decidir_reserva` para escribir el evento en la misma
  transacción. La actualización de cancelación escribe solo `estado` y
  `actualizado_en`, nunca `fecha_decision`.
- **Permisos**: `reservations/permissions.py` con las comprobaciones de cancelación
  y de visibilidad del historial.
- **Vistas y rutas**: listado de historial con filtros, confirmación de cancelación y
  ampliación del detalle; rutas `reservations:historial` y `reservations:cancelar`.
- **Plantillas**: `historial_lista.html`, `solicitud_cancelar.html`, ampliación de
  `solicitud_detalle.html` y enlace de navegación en `base.html`.
- **Pruebas**: nueva suite de cancelación, historial, inmutabilidad, atomicidad,
  filtros y control de acceso, con trazabilidad a `REQ-CAN-00X` y `REQ-HIS-00X`.
- **Dependencias internas**: requiere `solicitud-reserva`, `disponibilidad-simultaneidad`
  y `aprobacion-rechazo` implementados.
- **Dependencias externas**: ninguna nueva.
