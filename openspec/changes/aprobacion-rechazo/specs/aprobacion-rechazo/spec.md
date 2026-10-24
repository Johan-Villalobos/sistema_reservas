# Spec Delta

## Purpose

Permite a aprobadores y administradores revisar la cola de solicitudes pendientes,
aprobarlas o rechazarlas con trazabilidad, y comunica al solicitante el estado y el
motivo de la decisión, respetando la máquina de estados y la validación de
disponibilidad.

## ADDED Requirements

### Requirement: REQ-APR-001 Cola de solicitudes pendientes

Los usuarios con rol `APROBADOR` o `ADMINISTRADOR` SHALL poder listar las solicitudes
en estado `PENDIENTE`, ordenadas por fecha de reserva ascendente y, para la misma
fecha, por hora de inicio. El listado SHALL mostrar espacio, solicitante, fecha,
franja y motivo. Un `SOLICITANTE` SHALL recibir 403 y un visitante anónimo SHALL ser
redirigido al login.

#### Scenario: El aprobador ve solo las solicitudes pendientes ordenadas

- **GIVEN** solicitudes pendientes para el 10 de noviembre a las 10:00 y para el 9 de noviembre a las 09:00
- **AND** solicitudes aprobadas, rechazadas y canceladas en las mismas fechas
- **WHEN** un usuario con rol `APROBADOR` abre la cola de pendientes
- **THEN** la respuesta tiene estado 200
- **AND** la cola contiene únicamente las dos solicitudes pendientes
- **AND** la del 9 de noviembre aparece antes que la del 10 de noviembre

#### Scenario: El administrador también accede a la cola

- **GIVEN** un usuario con rol `ADMINISTRADOR`
- **WHEN** abre la cola de pendientes
- **THEN** la respuesta tiene estado 200
- **AND** ve las solicitudes pendientes

#### Scenario: Una cola vacía muestra un mensaje explícito

- **GIVEN** un usuario con rol `APROBADOR`
- **AND** no existen solicitudes pendientes
- **WHEN** abre la cola de pendientes
- **THEN** la respuesta tiene estado 200
- **AND** se muestra un mensaje que indica que no hay solicitudes pendientes

#### Scenario: El solicitante recibe 403 en la cola

- **GIVEN** un usuario autenticado con rol `SOLICITANTE`
- **WHEN** solicita la cola de pendientes
- **THEN** la respuesta tiene estado 403

#### Scenario: Anónimo es redirigido al login desde la cola

- **GIVEN** un visitante no autenticado
- **WHEN** solicita la cola de pendientes
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

### Requirement: REQ-APR-002 Aprobación de solicitudes pendientes

Un `APROBADOR` o `ADMINISTRADOR` SHALL poder aprobar una solicitud `PENDIENTE`
mediante una acción POST. La aprobación SHALL cambiar el estado a `APROBADA`, SHALL
registrar en `revisado_por` al usuario que decidió y SHALL fijar en `fecha_decision`
el instante de la decisión. El motivo de decisión SHALL quedar vacío en una
aprobación. `fecha_decision` SHALL ser un campo propio y distinto de `creado_en` y
`actualizado_en`.

#### Scenario: El aprobador aprueba una solicitud pendiente

- **GIVEN** una solicitud en estado `PENDIENTE` y un usuario con rol `APROBADOR` que no es su solicitante
- **WHEN** el aprobador envía la acción de aprobar
- **THEN** la solicitud pasa a estado `APROBADA`
- **AND** la respuesta redirige a la cola de pendientes

#### Scenario: La aprobación registra al revisor y la fecha de decisión

- **GIVEN** una solicitud pendiente y un aprobador distinto del solicitante
- **WHEN** se aprueba la solicitud
- **THEN** `revisado_por` corresponde al aprobador
- **AND** `fecha_decision` queda registrada con el instante de la aprobación
- **AND** el motivo de decisión queda vacío

#### Scenario: El administrador también puede aprobar

- **GIVEN** una solicitud pendiente y un usuario con rol `ADMINISTRADOR` que no es su solicitante
- **WHEN** envía la acción de aprobar
- **THEN** la solicitud pasa a estado `APROBADA`
- **AND** el administrador queda registrado como revisor

#### Scenario: Aprobar por GET no está permitido

- **GIVEN** una solicitud pendiente y un aprobador
- **WHEN** solicita la ruta de aprobación con el método GET
- **THEN** la respuesta tiene estado 405
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: Aprobar una solicitud inexistente devuelve 404

- **GIVEN** un aprobador autenticado
- **WHEN** envía la acción de aprobar para un identificador que no existe
- **THEN** la respuesta tiene estado 404

### Requirement: REQ-APR-003 Rechazo con motivo obligatorio

Un `APROBADOR` o `ADMINISTRADOR` SHALL poder rechazar una solicitud `PENDIENTE`
indicando un motivo. El motivo SHALL ser obligatorio y SHALL considerarse vacío si
está compuesto solo por espacios. Al rechazar, el estado SHALL pasar a `RECHAZADA`,
se SHALL registrar el revisor, el motivo normalizado en `motivo_decision` y el
instante de la decisión en `fecha_decision`.

#### Scenario: El aprobador rechaza con motivo

- **GIVEN** una solicitud pendiente y un aprobador distinto del solicitante
- **WHEN** envía el rechazo con un motivo válido
- **THEN** la solicitud pasa a estado `RECHAZADA`
- **AND** el motivo se guarda sin espacios sobrantes en los extremos
- **AND** el aprobador queda registrado como revisor
- **AND** `fecha_decision` queda registrada con el instante del rechazo
- **AND** la respuesta redirige a la cola de pendientes

#### Scenario: Rechazar sin motivo es inválido

- **GIVEN** una solicitud pendiente y un aprobador
- **WHEN** envía el rechazo con el motivo vacío
- **THEN** el rechazo se rechaza con un error en el motivo
- **AND** la solicitud permanece en estado `PENDIENTE`
- **AND** no se registra revisor ni motivo de decisión

#### Scenario: Un motivo compuesto solo por espacios es inválido

- **GIVEN** una solicitud pendiente y un aprobador
- **WHEN** envía el rechazo con un motivo formado únicamente por espacios o saltos de línea
- **THEN** el rechazo se rechaza con un error en el motivo
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: El administrador también puede rechazar

- **GIVEN** una solicitud pendiente y un usuario con rol `ADMINISTRADOR` que no es su solicitante
- **WHEN** envía el rechazo con un motivo válido
- **THEN** la solicitud pasa a estado `RECHAZADA`
- **AND** el administrador queda registrado como revisor

#### Scenario: El rechazo no exige validación de disponibilidad

- **GIVEN** una solicitud pendiente que se cruza con una reserva aprobada del mismo espacio y fecha
- **WHEN** un aprobador la rechaza con un motivo válido
- **THEN** la solicitud pasa a estado `RECHAZADA`
- **AND** no se reporta conflicto de disponibilidad

### Requirement: REQ-APR-004 Solo las solicitudes pendientes admiten decisión

Solo las solicitudes en estado `PENDIENTE` SHALL poder aprobarse o rechazarse.
Cualquier intento sobre una reserva `APROBADA`, `RECHAZADA` o `CANCELADA` SHALL
rechazarse con un mensaje claro y SHALL NOT modificar el estado, el revisor, el
motivo de decisión ni `fecha_decision`.

#### Scenario: Aprobar una solicitud ya aprobada falla

- **GIVEN** una solicitud en estado `APROBADA`
- **WHEN** un aprobador intenta aprobarla de nuevo
- **THEN** la operación se rechaza con un mensaje que indica que solo se pueden aprobar solicitudes pendientes
- **AND** la solicitud sigue en estado `APROBADA`

#### Scenario: Rechazar una solicitud cancelada falla

- **GIVEN** una solicitud en estado `CANCELADA`
- **WHEN** un aprobador intenta rechazarla
- **THEN** la operación se rechaza con un mensaje que indica que solo se pueden rechazar solicitudes pendientes
- **AND** la solicitud sigue en estado `CANCELADA`

#### Scenario: Aprobar una solicitud rechazada falla

- **GIVEN** una solicitud en estado `RECHAZADA`
- **WHEN** un aprobador intenta aprobarla
- **THEN** la operación se rechaza
- **AND** la solicitud sigue en estado `RECHAZADA`

#### Scenario: Rechazar una solicitud aprobada falla

- **GIVEN** una solicitud en estado `APROBADA`
- **WHEN** un aprobador intenta rechazarla
- **THEN** la operación se rechaza
- **AND** la solicitud sigue en estado `APROBADA`

#### Scenario: Un intento fallido no altera la decisión existente

- **GIVEN** una solicitud ya decidida, con revisor, motivo y `fecha_decision` registrados
- **WHEN** se intenta una nueva aprobación o un nuevo rechazo
- **THEN** el estado, el revisor, el motivo de decisión y `fecha_decision` conservan sus valores anteriores

### Requirement: REQ-APR-005 Prohibición de autodecisión

Un usuario SHALL NOT poder aprobar ni rechazar una solicitud de la que sea
solicitante, aunque tenga rol `APROBADOR` o `ADMINISTRADOR`. El intento SHALL
rechazarse sin modificar la solicitud.

#### Scenario: Un aprobador no puede aprobar su propia solicitud

- **GIVEN** un usuario con rol `APROBADOR` que creó una solicitud pendiente
- **WHEN** intenta aprobar su propia solicitud
- **THEN** la respuesta tiene estado 403
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: Un aprobador no puede rechazar su propia solicitud

- **GIVEN** un usuario con rol `APROBADOR` que creó una solicitud pendiente
- **WHEN** intenta rechazarla con un motivo válido
- **THEN** la respuesta tiene estado 403
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: Un administrador tampoco puede decidir su propia solicitud

- **GIVEN** un usuario con rol `ADMINISTRADOR` que creó una solicitud pendiente
- **WHEN** intenta aprobarla o rechazarla
- **THEN** la respuesta tiene estado 403
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: La cola marca la solicitud propia como no decidible

- **GIVEN** un aprobador con una solicitud pendiente propia y otra de otro usuario en la cola
- **WHEN** abre la cola de pendientes
- **THEN** ve ambas solicitudes
- **AND** la propia no ofrece los controles de aprobar ni rechazar
- **AND** se muestra una indicación de que no puede decidir sobre su propia solicitud

### Requirement: REQ-APR-006 Acceso restringido por rol

El rol `SOLICITANTE` SHALL NOT acceder a las acciones de aprobación ni de rechazo y
SHALL recibir una respuesta 403. Un visitante anónimo SHALL ser redirigido al login
con el parámetro `next`. Los roles `APROBADOR` y `ADMINISTRADOR` SHALL acceder a
ambas acciones.

#### Scenario: El solicitante intenta aprobar y recibe 403

- **GIVEN** un usuario autenticado con rol `SOLICITANTE`
- **WHEN** envía una acción de aprobación sobre una solicitud pendiente
- **THEN** la respuesta tiene estado 403
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: El solicitante intenta rechazar y recibe 403

- **GIVEN** un usuario autenticado con rol `SOLICITANTE`
- **WHEN** solicita el formulario de rechazo de una solicitud pendiente
- **THEN** la respuesta tiene estado 403

#### Scenario: Anónimo es redirigido al login desde la aprobación

- **GIVEN** un visitante no autenticado
- **WHEN** envía una acción de aprobación
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

#### Scenario: Anónimo es redirigido al login desde el rechazo

- **GIVEN** un visitante no autenticado
- **WHEN** solicita el formulario de rechazo
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

#### Scenario: El aprobador accede al formulario de rechazo

- **GIVEN** un usuario con rol `APROBADOR` y una solicitud pendiente ajena
- **WHEN** solicita el formulario de rechazo
- **THEN** la respuesta tiene estado 200
- **AND** el formulario muestra el campo de motivo

### Requirement: REQ-APR-007 Visibilidad de la decisión para el solicitante

El solicitante SHALL ver en el detalle de su solicitud el estado actual y, cuando
exista, el motivo de la decisión y el usuario que la revisó. El motivo SHALL mostrarse
íntegro. La visibilidad del detalle SHALL seguir las reglas de `solicitud-reserva`.

#### Scenario: El solicitante ve una solicitud aprobada

- **GIVEN** una solicitud aprobada por un revisor
- **WHEN** su solicitante abre el detalle
- **THEN** la respuesta tiene estado 200
- **AND** se muestra el estado `APROBADA`
- **AND** se muestra el usuario que la revisó
- **AND** no se muestra un motivo de rechazo

#### Scenario: El solicitante ve el motivo del rechazo

- **GIVEN** una solicitud rechazada con un motivo
- **WHEN** su solicitante abre el detalle
- **THEN** la respuesta tiene estado 200
- **AND** se muestra el estado `RECHAZADA`
- **AND** se muestra el motivo completo de la decisión
- **AND** se muestra el usuario que la revisó

#### Scenario: Una solicitud pendiente no muestra datos de decisión

- **GIVEN** una solicitud en estado `PENDIENTE`
- **WHEN** su solicitante abre el detalle
- **THEN** se muestra el estado `PENDIENTE`
- **AND** no se muestra revisor ni motivo de decisión

#### Scenario: Otro solicitante no puede ver el detalle

- **GIVEN** una solicitud decidida y un usuario con rol `SOLICITANTE` que no es su dueño
- **WHEN** intenta abrir el detalle
- **THEN** la respuesta tiene estado 403
- **AND** no se muestra el motivo de la decisión

### Requirement: REQ-APR-008 Validación de disponibilidad al aprobar

La aprobación SHALL aplicar la validación de cruces de la capacidad `disponibilidad`
dentro de la transacción de decisión. Si existe conflicto con una reserva `APROBADA`,
la aprobación SHALL rechazarse con un mensaje que identifique el espacio, la fecha y
la franja ocupada, y la solicitud SHALL permanecer `PENDIENTE`.

#### Scenario: Aprobar una solicitud que ahora se cruza falla con mensaje claro

- **GIVEN** una solicitud pendiente de 10:00 a 12:00
- **AND** una reserva aprobada de 11:00 a 13:00 en el mismo espacio y fecha
- **WHEN** un aprobador intenta aprobar la solicitud pendiente
- **THEN** la aprobación se rechaza
- **AND** el mensaje menciona el espacio, la fecha y la franja de 11:00 a 13:00
- **AND** la solicitud permanece en estado `PENDIENTE`
- **AND** no se registra revisor

#### Scenario: La revalidación detecta un conflicto creado después de la solicitud

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 creada cuando el espacio estaba libre
- **AND** una reserva aprobada de 10:00 a 11:00 registrada después en el mismo espacio y fecha
- **WHEN** un aprobador intenta aprobar la solicitud pendiente
- **THEN** la aprobación se rechaza por conflicto de disponibilidad
- **AND** la solicitud permanece en estado `PENDIENTE`

#### Scenario: Dos solicitudes pendientes que se cruzan: la segunda falla

- **GIVEN** dos solicitudes pendientes de 10:00 a 12:00 y de 11:00 a 13:00 en el mismo espacio y fecha
- **WHEN** se aprueba la primera y luego se intenta aprobar la segunda
- **THEN** la primera queda en estado `APROBADA`
- **AND** la segunda permanece en estado `PENDIENTE`
- **AND** la segunda aprobación se rechaza por conflicto de disponibilidad

#### Scenario: Una solicitud sin conflicto se aprueba

- **GIVEN** una solicitud pendiente de 10:00 a 12:00 sin reservas aprobadas que se crucen
- **WHEN** un aprobador la aprueba
- **THEN** la solicitud queda en estado `APROBADA`
- **AND** el aprobador queda registrado como revisor
