# Spec Delta

## Purpose

Detecta y previene cruces de reservas en un mismo espacio y fecha, define qué
estados bloquean el espacio, aplica la regla de forma idéntica al crear y al aprobar
solicitudes dentro de una transacción, y permite consultar las franjas ocupadas por
reservas aprobadas.

## ADDED Requirements

### Requirement: REQ-DIS-001 Regla de cruce de franjas

El sistema SHALL considerar que dos reservas del mismo espacio y la misma fecha se
cruzan cuando `inicio_A < fin_B` y `fin_A > inicio_B`. La comparación SHALL usar horas
de inicio y fin dentro de la fecha de cada reserva.

#### Scenario: Cruce total con una reserva aprobada es rechazado

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en un espacio y fecha
- **WHEN** se intenta crear una solicitud de 10:00 a 12:00 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad
- **AND** no se crea la reserva

#### Scenario: Cruce parcial al inicio es rechazado

- **GIVEN** una reserva aprobada de 10:00 a 12:00
- **WHEN** se intenta crear una solicitud de 09:00 a 11:00 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad

#### Scenario: Cruce parcial al final es rechazado

- **GIVEN** una reserva aprobada de 10:00 a 12:00
- **WHEN** se intenta crear una solicitud de 11:00 a 13:00 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad

#### Scenario: Solicitud contenida dentro de otra aprobada es rechazada

- **GIVEN** una reserva aprobada de 10:00 a 12:00
- **WHEN** se intenta crear una solicitud de 10:30 a 11:30 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad

#### Scenario: Solicitud que contiene a otra aprobada es rechazada

- **GIVEN** una reserva aprobada de 10:00 a 12:00
- **WHEN** se intenta crear una solicitud de 09:00 a 13:00 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad

### Requirement: REQ-DIS-002 Solo las reservas aprobadas bloquean el espacio

Solo las reservas en estado `APROBADA` SHALL bloquear un espacio. Las reservas
`PENDIENTE`, `RECHAZADA` y `CANCELADA` SHALL NOT bloquearlo ni impedir nuevas
solicitudes en la misma franja.

#### Scenario: Una reserva PENDIENTE no bloquea

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 en un espacio y fecha
- **WHEN** se crea otra solicitud de 10:00 a 12:00 en el mismo espacio y fecha
- **THEN** la nueva solicitud se crea en estado `PENDIENTE`
- **AND** no se reporta conflicto de disponibilidad

#### Scenario: Una reserva CANCELADA libera el horario

- **GIVEN** una reserva cancelada de 10:00 a 12:00 en un espacio y fecha
- **WHEN** se crea una solicitud de 10:00 a 12:00 en el mismo espacio y fecha
- **THEN** la solicitud se crea correctamente
- **AND** no se reporta conflicto de disponibilidad

#### Scenario: Una reserva RECHAZADA no bloquea

- **GIVEN** una reserva rechazada de 10:00 a 12:00 en un espacio y fecha
- **WHEN** se crea una solicitud de 10:00 a 12:00 en el mismo espacio y fecha
- **THEN** la solicitud se crea correctamente

### Requirement: REQ-DIS-003 Rechazo de la creación con mensaje claro

Al crear una solicitud, el sistema SHALL rechazarla si se cruza con una reserva
`APROBADA` del mismo espacio y fecha, e SHALL informar un mensaje que identifique el
espacio, la fecha y la franja ocupada que genera el conflicto.

#### Scenario: La creación informa el espacio, la fecha y la franja en conflicto

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en el Auditorio Principal para una fecha futura
- **WHEN** un usuario intenta solicitar el mismo espacio y fecha de 11:00 a 13:00
- **THEN** el formulario muestra un mensaje de conflicto
- **AND** el mensaje menciona el espacio, la fecha y la franja de 10:00 a 12:00

### Requirement: REQ-DIS-004 Reservas contiguas permitidas

Las reservas contiguas SHALL permitirse: si una termina exactamente a la hora en que
empieza la otra, no SHALL considerarse conflicto. Un solapamiento de un minuto o más
SHALL rechazarse.

#### Scenario: Una reserva que empieza al terminar otra es aceptada

- **GIVEN** una reserva aprobada de 10:00 a 12:00
- **WHEN** se crea una solicitud de 12:00 a 14:00 en el mismo espacio y fecha
- **THEN** la solicitud se crea correctamente

#### Scenario: Una reserva que termina al empezar otra es aceptada

- **GIVEN** una reserva aprobada de 12:00 a 14:00
- **WHEN** se crea una solicitud de 10:00 a 12:00 en el mismo espacio y fecha
- **THEN** la solicitud se crea correctamente

#### Scenario: Un solapamiento de un minuto es rechazado

- **GIVEN** una reserva aprobada de 10:00 a 11:00
- **WHEN** se intenta crear una solicitud de 10:59 a 12:00 en el mismo espacio y fecha
- **THEN** la solicitud se rechaza por conflicto de disponibilidad

### Requirement: REQ-DIS-005 Independencia de espacio y fecha

Reservas de espacios distintos o de fechas distintas SHALL NOT considerarse en
conflicto, aunque compartan la misma franja horaria.

#### Scenario: Mismo horario en otro espacio es permitido

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en el espacio A para una fecha
- **WHEN** se crea una solicitud de 10:00 a 12:00 en el espacio B para la misma fecha
- **THEN** la solicitud se crea correctamente

#### Scenario: Mismo horario en otra fecha es permitido

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en un espacio para una fecha
- **WHEN** se crea una solicitud de 10:00 a 12:00 en el mismo espacio para el día siguiente
- **THEN** la solicitud se crea correctamente

### Requirement: REQ-DIS-006 Revalidación al aprobar en transacción atómica

Al aprobar una solicitud, el sistema SHALL volver a validar el cruce dentro de una
transacción atómica y SHALL impedir la aprobación si existe conflicto con una reserva
aprobada. Un intento rechazado SHALL dejar la solicitud en su estado anterior.

#### Scenario: Aprobar una solicitud que se cruza con una aprobada falla

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 y una reserva aprobada de 11:00 a 13:00 en el mismo espacio y fecha
- **WHEN** se intenta aprobar la solicitud pendiente
- **THEN** la aprobación se rechaza por conflicto de disponibilidad
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: La revalidación detecta un conflicto creado después de la solicitud

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 creada cuando el espacio estaba libre
- **AND** una reserva aprobada de 10:00 a 11:00 registrada después en el mismo espacio y fecha
- **WHEN** se intenta aprobar la solicitud pendiente
- **THEN** la aprobación se rechaza por conflicto de disponibilidad
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: Una solicitud sin conflicto se aprueba

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 sin reservas aprobadas que se crucen
- **WHEN** se aprueba la solicitud
- **THEN** la solicitud queda en estado `APROBADA`

### Requirement: REQ-DIS-007 Dos solicitudes pendientes que se cruzan

Si dos solicitudes que se cruzan están `PENDIENTE`, la aprobación de una SHALL
provocar que la otra no pueda aprobarse mientras la primera siga `APROBADA`.

#### Scenario: Aprobar dos pendientes que se cruzan: la segunda falla

- **GIVEN** dos solicitudes pendientes de 10:00 a 12:00 y de 11:00 a 13:00 en el mismo espacio y fecha
- **WHEN** se aprueba la primera y luego se intenta aprobar la segunda
- **THEN** la primera queda en estado `APROBADA`
- **AND** la segunda permanece en estado `PENDIENTE`
- **AND** la segunda aprobación se rechaza por conflicto de disponibilidad

La liberación de la franja cuando una reserva aprobada deja de estarlo pertenece a
`cancelacion-historial` (REQ-CAN-005); este cambio no define esa transición.

### Requirement: REQ-DIS-008 Consulta de disponibilidad por espacio y fecha

El sistema SHALL permitir consultar las franjas ocupadas de un espacio en una fecha.
La consulta SHALL calcularse en cada petición a partir de las reservas `APROBADA`
vigentes, sin caché ni dato denormalizado, y SHALL mostrar únicamente esas franjas
ordenadas por hora de inicio. El alcance SHALL limitarse a las franjas ocupadas: el
cálculo de franjas libres, sugerencias de horario y disponibilidad agregada quedan
fuera de alcance. La consulta SHALL requerir autenticación.

#### Scenario: La consulta lista solo franjas aprobadas

- **GIVEN** un espacio con una reserva aprobada de 10:00 a 12:00, una pendiente de 14:00 a 16:00 y una cancelada de 08:00 a 09:00 en la misma fecha
- **WHEN** un usuario autenticado consulta la disponibilidad de ese espacio y fecha
- **THEN** la respuesta tiene estado 200
- **AND** muestra la franja de 10:00 a 12:00 como ocupada
- **AND** no muestra las franjas de 14:00 a 16:00 ni de 08:00 a 09:00

#### Scenario: Una fecha sin reservas aprobadas se muestra libre

- **GIVEN** un espacio sin reservas aprobadas en una fecha
- **WHEN** un usuario autenticado consulta su disponibilidad
- **THEN** la respuesta tiene estado 200
- **AND** indica que no hay franjas ocupadas

#### Scenario: La consulta se recalcula en cada petición

- **GIVEN** una consulta de disponibilidad de un espacio y fecha sin franjas ocupadas
- **WHEN** se aprueba una reserva de 10:00 a 12:00 para ese espacio y fecha
- **AND** se repite la misma consulta
- **THEN** la nueva respuesta muestra la franja de 10:00 a 12:00 como ocupada
- **AND** no se reutiliza el resultado de la consulta anterior

#### Scenario: Anónimo es redirigido al login desde la disponibilidad

- **GIVEN** un visitante no autenticado
- **WHEN** solicita la consulta de disponibilidad
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

### Requirement: REQ-DIS-009 Validación única reutilizada al crear y aprobar

La validación de cruces SHALL implementarse en una única función de servicio
reutilizada por la creación y por la aprobación. Ambas rutas SHALL producir el mismo
resultado y el mismo mensaje ante un conflicto equivalente.

#### Scenario: Creación y aprobación usan la misma regla

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en un espacio y fecha
- **WHEN** se intenta crear una solicitud de 11:00 a 12:00 y, por separado, se intenta aprobar una solicitud pendiente de 11:00 a 12:00 para el mismo espacio y fecha
- **THEN** ambas operaciones se rechazan por conflicto de disponibilidad
- **AND** el mensaje de conflicto es equivalente en ambos casos
