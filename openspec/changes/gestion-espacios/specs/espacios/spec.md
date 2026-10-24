# Spec Delta

## Purpose

Gestiona el catálogo de espacios académicos de la institución —laboratorios,
auditorios y salas de cómputo— con su clasificación, capacidad, ubicación, estado
lógico y reglas de validación, y ofrece su consulta filtrada a los usuarios
autenticados y su administración exclusiva al rol administrador.

## ADDED Requirements

### Requirement: REQ-ESP-001 Datos del espacio académico

El sistema SHALL gestionar espacios académicos con los campos nombre, tipo,
capacidad, ubicación, descripción y estado activo. Todo espacio creado SHALL quedar
activo por defecto y SHALL conservar ubicación y descripción como datos editables.

#### Scenario: El administrador crea un laboratorio válido

- **GIVEN** un administrador autenticado
- **WHEN** registra un espacio con nombre, tipo `LABORATORIO`, capacidad, ubicación y descripción válidos
- **THEN** el espacio se crea con estado activo
- **AND** el espacio aparece en el catálogo con todos sus datos

#### Scenario: La ubicación y la descripción se conservan al editar

- **GIVEN** un espacio existente con ubicación y descripción
- **WHEN** el administrador modifica la ubicación y la descripción
- **THEN** el detalle del espacio muestra los nuevos valores
- **AND** el resto de los campos permanece sin cambios

### Requirement: REQ-ESP-002 Tipos de espacio permitidos

El tipo de un espacio SHALL ser uno de `LABORATORIO`, `AUDITORIO` o
`SALA_COMPUTO`. Cualquier otro valor SHALL rechazarse sin crear ni modificar el
espacio.

#### Scenario: Tipo inválido es rechazado

- **GIVEN** un administrador autenticado en el formulario de creación
- **WHEN** envía un tipo distinto de los tres permitidos
- **THEN** la operación se rechaza con un error en el campo tipo
- **AND** no se crea ningún espacio

#### Scenario: Cada tipo permitido puede registrarse

- **GIVEN** un administrador autenticado
- **WHEN** crea un espacio para cada tipo `LABORATORIO`, `AUDITORIO` y `SALA_COMPUTO`
- **THEN** los tres espacios se crean correctamente
- **AND** cada uno conserva el tipo enviado

### Requirement: REQ-ESP-003 Nombre único sin distinguir mayúsculas

El nombre del espacio SHALL ser único sin distinguir mayúsculas de minúsculas. Un
intento de crear o renombrar un espacio con un nombre ya existente SHALL rechazarse
y no SHALL modificar el registro original.

#### Scenario: Nombre duplicado en distinta capitalización es rechazado

- **GIVEN** un espacio registrado con el nombre "Auditorio Principal"
- **WHEN** el administrador intenta crear otro espacio llamado "AUDITORIO PRINCIPAL"
- **THEN** la operación se rechaza con un error en el campo nombre
- **AND** existe un solo espacio con ese nombre

#### Scenario: Renombrar a un nombre existente es rechazado

- **GIVEN** dos espacios con nombres distintos
- **WHEN** el administrador intenta renombrar uno con el nombre del otro en otra capitalización
- **THEN** la operación se rechaza con un error en el campo nombre
- **AND** ambos espacios conservan sus nombres originales

### Requirement: REQ-ESP-004 Capacidad entera mayor que cero

La capacidad de un espacio SHALL ser un número entero mayor que cero. Un valor cero,
negativo o no entero SHALL rechazarse sin crear ni modificar el espacio.

#### Scenario: Capacidad cero o negativa es rechazada

- **GIVEN** un administrador autenticado en el formulario de creación
- **WHEN** envía una capacidad de 0 o un valor negativo
- **THEN** la operación se rechaza con un error en el campo capacidad
- **AND** no se crea ningún espacio

#### Scenario: Capacidad no entera es rechazada

- **GIVEN** un administrador autenticado en el formulario de creación
- **WHEN** envía una capacidad con decimales o texto
- **THEN** la operación se rechaza con un error en el campo capacidad
- **AND** no se crea ningún espacio

### Requirement: REQ-ESP-005 Administración exclusiva del ADMINISTRADOR

Solo el rol `ADMINISTRADOR` SHALL poder crear, editar y desactivar espacios. Un
usuario autenticado con otro rol SHALL recibir una respuesta 403 y un visitante
anónimo SHALL ser redirigido al inicio de sesión.

#### Scenario: SOLICITANTE intenta crear un espacio y recibe 403

- **GIVEN** un usuario autenticado con rol `SOLICITANTE`
- **WHEN** solicita el formulario de creación o envía los datos de un espacio
- **THEN** la respuesta tiene estado 403
- **AND** no se crea ningún espacio

#### Scenario: Usuario anónimo es redirigido al login

- **GIVEN** un visitante no autenticado
- **WHEN** solicita el catálogo, el detalle o el formulario de creación de espacios
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

#### Scenario: El APROBADOR tampoco administra espacios

- **GIVEN** un usuario autenticado con rol `APROBADOR`
- **WHEN** intenta editar o desactivar un espacio
- **THEN** la respuesta tiene estado 403
- **AND** el espacio no se modifica

### Requirement: REQ-ESP-006 Desactivación lógica sin eliminación

Un espacio SHALL desactivarse en lugar de eliminarse: el registro SHALL permanecer
almacenado con su estado activo en falso, de modo que se conserve el historial de
reservas. El sistema no SHALL ofrecer eliminación física de espacios.

#### Scenario: El administrador desactiva un espacio y deja de aparecer para los solicitantes

- **GIVEN** un espacio activo y un usuario con rol `SOLICITANTE`
- **WHEN** el administrador desactiva el espacio
- **THEN** el espacio queda con estado inactivo y sigue existiendo en la base de datos
- **AND** el solicitante ya no lo ve en su catálogo

#### Scenario: El espacio desactivado sigue visible para el administrador

- **GIVEN** un espacio inactivo
- **WHEN** el administrador abre el catálogo
- **THEN** el espacio aparece identificado como inactivo
- **AND** el administrador puede abrir su detalle

#### Scenario: No existe eliminación física de espacios

- **GIVEN** un espacio registrado
- **WHEN** se revisan las rutas y acciones disponibles del módulo
- **THEN** no existe una operación de borrado definitivo
- **AND** la única transición de estado disponible es la desactivación

### Requirement: REQ-ESP-007 Catálogo filtrado por tipo según el rol

Todo usuario autenticado SHALL poder listar los espacios activos y filtrarlos por
tipo. El `ADMINISTRADOR` SHALL ver además los espacios inactivos. El filtro SHALL
devolver únicamente los espacios del tipo solicitado.

#### Scenario: Filtro por tipo devuelve solo los espacios de ese tipo

- **GIVEN** espacios activos de los tres tipos y un usuario autenticado
- **WHEN** filtra el catálogo por `LABORATORIO`
- **THEN** el listado contiene únicamente espacios de tipo `LABORATORIO`
- **AND** no incluye auditorios ni salas de cómputo

#### Scenario: El solicitante solo ve espacios activos

- **GIVEN** espacios activos e inactivos y un usuario con rol `SOLICITANTE`
- **WHEN** abre el catálogo sin filtro
- **THEN** el listado incluye los espacios activos
- **AND** no incluye los inactivos

#### Scenario: El administrador ve también los inactivos

- **GIVEN** espacios activos e inactivos
- **WHEN** el administrador abre el catálogo
- **THEN** el listado incluye espacios activos e inactivos
- **AND** cada espacio inactivo se distingue visualmente del activo

### Requirement: REQ-ESP-008 Detalle del espacio

El sistema SHALL mostrar el detalle de un espacio a los usuarios autenticados,
incluyendo nombre, tipo, capacidad, ubicación, descripción y estado. El detalle de un
espacio inactivo SHALL estar disponible solo para el `ADMINISTRADOR`.

#### Scenario: Un usuario autenticado consulta el detalle

- **GIVEN** un espacio activo y un usuario autenticado
- **WHEN** solicita el detalle de ese espacio
- **THEN** la respuesta tiene estado 200
- **AND** muestra nombre, tipo, capacidad, ubicación, descripción y estado

#### Scenario: Un espacio inexistente devuelve 404

- **GIVEN** un usuario autenticado
- **WHEN** solicita el detalle de un identificador que no existe
- **THEN** la respuesta tiene estado 404

#### Scenario: El solicitante no accede al detalle de un espacio inactivo

- **GIVEN** un espacio inactivo y un usuario con rol `SOLICITANTE`
- **WHEN** solicita el detalle de ese espacio
- **THEN** la respuesta tiene estado 404
- **AND** no se muestran sus datos
