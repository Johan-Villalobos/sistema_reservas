# Proposal

## Why

El sistema ya permite crear solicitudes y validar cruces, pero las solicitudes se
quedan en `PENDIENTE` para siempre: no hay forma de aprobarlas ni de rechazarlas, y
el solicitante no recibe ninguna decisión. Sin este flujo, el ciclo de vida del plan
2.5 queda incompleto y la institución sigue conciliando aprobaciones por fuera del
sistema. Este cambio cierra ese ciclo con la máquina de estados mínima y la
trazabilidad de quién decidió y por qué.

## What Changes

- Se agregan a `Reserva` los campos `revisado_por` (usuario que decide),
  `motivo_decision` (justificación del rechazo) y `fecha_decision` (instante de la
  decisión, distinto de `actualizado_en`), mediante una migración.
- Los roles `APROBADOR` y `ADMINISTRADOR` pueden listar las solicitudes `PENDIENTE`
  ordenadas por fecha de reserva.
- Se completa `aprobar_reserva`: pasa una solicitud `PENDIENTE` a `APROBADA`,
  registra al revisor, fija `fecha_decision` y aplica la validación de cruces de la
  capacidad `disponibilidad`.
- Se implementa `rechazar_reserva`: pasa una solicitud `PENDIENTE` a `RECHAZADA` con
  motivo obligatorio, registra al revisor y fija `fecha_decision`.
- Se implementa una máquina de estados explícita: solo `PENDIENTE → APROBADA` y
  `PENDIENTE → RECHAZADA` son transiciones válidas; cualquier otra se rechaza sin
  modificar la reserva.
- Se impide que un usuario apruebe o rechace su propia solicitud. Es una decisión
  nueva, no presente en el plan, y queda marcada para confirmar en la revisión.
- El rol `SOLICITANTE` no accede a las vistas de aprobación ni de rechazo y recibe
  403; un visitante anónimo es redirigido al login.
- El solicitante ve el estado y, cuando existe, el motivo de la decisión en el
  detalle de su solicitud.
- Se conserva el nombre canónico `aprobar_reserva` que introdujo `disponibilidad` y
  se completa su comportamiento con la máquina de estados y la trazabilidad, sin
  renombrar la función.

Fuera de alcance: la cancelación por parte del solicitante, el historial
`HistorialReserva`, la edición de solicitudes aprobadas, la notificación por correo,
la aprobación masiva y la reactivación de una solicitud rechazada. El historial y la
cancelación se abordan en un cambio posterior.

## Capabilities

### New Capabilities

- `aprobacion-rechazo`: cola de solicitudes pendientes para aprobadores y
  administradores, decisión de aprobar o rechazar con trazabilidad, máquina de
  estados del ciclo de vida, prohibición de autodecisión, control de acceso por rol y
  comunicación de la decisión al solicitante.

### Modified Capabilities

- `disponibilidad`: conserva su regla de cruces y su revalidación, pero la función
  mínima `aprobar_reserva` que introdujo pasa a tener la máquina de estados y la
  trazabilidad completas en este cambio. El nombre canónico no cambia.
- `solicitud-reserva`: la especificación ya había diferido `revisado_por` y
  `motivo_decision`; este cambio los agrega junto con `fecha_decision` y mantiene el
  resto del contrato de `Reserva`.

## Impact

- **Modelo y migración**: `reservations/models.py` con `revisado_por`
  (`ForeignKey` nullable a `settings.AUTH_USER_MODEL`, `SET_NULL`,
  `related_name="reservas_revisadas"`), `motivo_decision` (texto opcional) y
  `fecha_decision` (`DateTimeField` nullable); `reservations/migrations/0002_...`
  correspondiente.
- **Servicios**: `reservations/services.py` completa `aprobar_reserva` y agrega
  `rechazar_reserva` y la máquina de estados compartida, sin renombrar la función
  existente.
- **Vistas y rutas**: cola de pendientes, aprobación y rechazo protegidas por rol,
  más las rutas `reservations:pendientes`, `reservations:aprobar` y
  `reservations:rechazar`.
- **Formularios**: `RechazarReservaForm` con motivo obligatorio y normalización de
  espacios.
- **Plantillas**: `solicitud_pendientes.html`, `solicitud_rechazar.html` y
  actualización de `solicitud_detalle.html` y de la navegación en `base.html`.
- **Pruebas**: nueva suite de aprobación y rechazo, ampliación de detalle y prueba de
  que la cancelación posterior conserva `fecha_decision` (en el cambio de cancelación).
- **Dependencias internas**: requiere `solicitud-reserva` y
  `disponibilidad-simultaneidad` implementados.
- **Dependencias externas**: ninguna nueva.
