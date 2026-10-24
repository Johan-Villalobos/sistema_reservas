# Spec Delta

## Purpose

Establece la fundación técnica del sistema de gestión de reservas de espacios
académicos: la estructura del monolito Django con sus cuatro aplicaciones, la
configuración regional y de base de datos, la higiene del repositorio, la plantilla
base con navegación según autenticación, la separación de reglas de negocio en un
módulo de servicios por aplicación, la carga idempotente de datos de ejemplo y las
pruebas de arranque y migración que habilitan todos los incrementos posteriores.

## ADDED Requirements

### Requirement: REQ-BAS-001 Estructura del monolito Django

El proyecto SHALL ser un monolito Django con arquitectura MVT y cuatro aplicaciones
—`core`, `accounts`, `spaces` y `reservations`— registradas en
`INSTALLED_APPS`, dentro del paquete de configuración `config`. Cada aplicación
SHALL exponer los archivos propios de MVT (`models.py`, `views.py`, `urls.py`,
`templates/` y `tests/`), y las aplicaciones de dominio `accounts`, `spaces` y
`reservations` SHALL incluir además `services.py` como punto único de sus reglas de
negocio.

#### Scenario: Las cuatro aplicaciones están registradas y son importables

- **GIVEN** el repositorio recién clonado con las dependencias instaladas
- **WHEN** se ejecuta el comando de verificación del proyecto (`manage.py check`)
- **THEN** el comando termina sin errores
- **AND** `INSTALLED_APPS` incluye `core`, `accounts`, `spaces` y `reservations`
- **AND** el módulo de configuración se importa como `config.settings`
- **AND** los módulos `accounts.services`, `spaces.services` y `reservations.services`
  son importables

#### Scenario: La aplicación core sirve la ruta raíz

- **GIVEN** el proyecto configurado
- **WHEN** se resuelve la URL `/`
- **THEN** el enrutamiento apunta a una vista de la aplicación `core`
- **AND** no se produce un error de resolución de URL

### Requirement: REQ-BAS-002 Configuración regional y de base de datos

La configuración SHALL usar SQLite local con el archivo `db.sqlite3` en la raíz del
proyecto, `TIME_ZONE` igual a `America/Bogota`, `USE_TZ` activado y `LANGUAGE_CODE`
igual a `es-co`. Las fechas y horas mostradas por el sistema SHALL respetar la zona
horaria configurada.

#### Scenario: Los valores de configuración son los exigidos

- **GIVEN** el proyecto configurado
- **WHEN** se inspeccionan los ajustes efectivos de Django
- **THEN** el motor de base de datos es `django.db.backends.sqlite3`
- **AND** el nombre de la base de datos apunta a `db.sqlite3`
- **AND** `TIME_ZONE` es `America/Bogota`
- **AND** `USE_TZ` es verdadero
- **AND** `LANGUAGE_CODE` es `es-co`

#### Scenario: La fecha mostrada usa la zona horaria de Bogotá

- **GIVEN** un usuario que abre la página de inicio
- **WHEN** la plantilla renderiza una fecha u hora del sistema
- **THEN** el valor mostrado corresponde a la hora local de `America/Bogota`
- **AND** el texto de la interfaz se presenta en español de Colombia

### Requirement: REQ-BAS-003 Exclusión de artefactos locales del repositorio

El archivo `db.sqlite3` SHALL estar excluido del repositorio mediante `.gitignore`,
junto con el directorio del entorno virtual y los archivos `*.pyc` (incluido
`__pycache__/`).

#### Scenario: Git ignora la base de datos, el entorno virtual y los bytecode

- **GIVEN** el repositorio con `.gitignore` versionado
- **WHEN** se ejecuta `git check-ignore -v` sobre `db.sqlite3`, `venv/` y un archivo
  `modulo.pyc`
- **THEN** Git reporta las tres rutas como ignoradas
- **AND** `git status` no muestra `db.sqlite3` entre los archivos sin seguimiento

#### Scenario: El archivo de base de datos no se versiona

- **GIVEN** una base de datos local creada tras ejecutar las migraciones
- **WHEN** se revisa el contenido versionado del repositorio
- **THEN** `db.sqlite3` no aparece en el índice de Git

### Requirement: REQ-BAS-004 Migraciones aplicables sobre base de datos vacía

Las migraciones SHALL aplicarse sobre una base de datos vacía mediante `migrate`, sin
errores ni migraciones pendientes. La primera migración de `accounts` SHALL crear el
`Usuario` mínimo declarado como `AUTH_USER_MODEL`, sin crear `auth_user`. Los campos
de dominio del usuario SHALL agregarse después con migraciones nuevas.

#### Scenario: Migrate en base limpia termina sin errores

- **GIVEN** una base de datos vacía (archivo inexistente o eliminado)
- **WHEN** se ejecuta `python manage.py migrate`
- **THEN** el comando termina con código de salida 0
- **AND** no se reporta ninguna migración fallida ni pendiente
- **AND** existe la tabla `accounts_usuario`
- **AND** no existe la tabla `auth_user` del usuario por defecto de Django

#### Scenario: La primera migración crea el usuario personalizado

- **GIVEN** una base de datos vacía y la configuración `AUTH_USER_MODEL = "accounts.Usuario"`
- **WHEN** se ejecutan las migraciones
- **THEN** `get_user_model()` devuelve el modelo `accounts.Usuario`
- **AND** la tabla `accounts_usuario` contiene las columnas heredadas del usuario de
  Django (`username`, `email`, `password`, `is_active`)
- **AND** el modelo no incluye todavía los campos de dominio que agrega `accounts`
- **AND** los cambios posteriores agregan esos campos con una migración nueva sin
  regenerar la inicial

#### Scenario: Las migraciones son reproducibles desde cero

- **GIVEN** una base de datos con las migraciones ya aplicadas
- **WHEN** se elimina la base de datos y se vuelve a ejecutar `migrate`
- **THEN** el esquema se reconstruye sin errores
- **AND** el resultado es equivalente al de la primera aplicación

### Requirement: REQ-BAS-005 Plantilla base con navegación según autenticación

El sistema SHALL disponer de la plantilla `templates/base.html` que incluya
Bootstrap 5 y una barra de navegación cuyos enlaces cambian según que el usuario
esté autenticado o no. La página de inicio SHALL renderizarse con esa plantilla y
responder con estado HTTP 200.

#### Scenario: La página de inicio responde 200

- **GIVEN** el proyecto en ejecución con la base de datos migrada
- **WHEN** un cliente solicita la ruta `/`
- **THEN** la respuesta tiene estado HTTP 200
- **AND** el cuerpo incluye el marcado de la plantilla base

#### Scenario: La plantilla base muestra enlaces para usuario anónimo

- **GIVEN** un visitante no autenticado
- **WHEN** se renderiza `base.html`
- **THEN** la navegación muestra los enlaces de inicio de sesión y de registro
- **AND** no muestra enlaces reservados a usuarios autenticados

#### Scenario: La plantilla base muestra enlaces para usuario autenticado

- **GIVEN** un usuario autenticado
- **WHEN** se renderiza `base.html`
- **THEN** la navegación muestra el enlace de cierre de sesión y el acceso a las
  secciones del usuario
- **AND** no muestra los enlaces de inicio de sesión ni de registro

### Requirement: REQ-BAS-006 Dependencias fijadas por versión

El proyecto SHALL incluir `requirements.txt` con todas las dependencias directas
fijadas por versión con el operador `==`, de modo que una instalación nueva
reproduzca el mismo entorno.

#### Scenario: Todas las dependencias están fijadas

- **GIVEN** el archivo `requirements.txt` versionado
- **WHEN** se inspeccionan sus líneas de dependencia
- **THEN** cada dependencia declara una versión exacta con `==`
- **AND** Django figura como dependencia directa

#### Scenario: Una instalación nueva reproduce el entorno

- **GIVEN** un entorno virtual vacío
- **WHEN** se ejecuta `pip install -r requirements.txt`
- **THEN** la instalación termina sin errores
- **AND** la versión instalada de Django coincide con la declarada

### Requirement: REQ-BAS-007 Reglas de negocio aisladas en el servicio de cada aplicación

Las reglas de negocio SHALL ubicarse en el `services.py` de la aplicación que posee la
regla: `accounts`, `spaces` o `reservations`. Las vistas SHALL limitarse a orquestar:
recibir la petición, invocar el servicio y elegir la respuesta. Se considera regla toda
validación o transición que no dependa del formato de la petición y pueda probarse sin
cliente HTTP.

#### Scenario: Cada aplicación de dominio expone su propio módulo de servicios

- **GIVEN** las aplicaciones `accounts`, `spaces` y `reservations`
- **WHEN** se inspecciona su estructura
- **THEN** existen los módulos `accounts/services.py`, `spaces/services.py` y
  `reservations/services.py`
- **AND** `accounts/services.py` concentra identidad y roles, `spaces/services.py` la
  normalización y validación del catálogo, y `reservations/services.py` la
  disponibilidad y las transiciones de reserva
- **AND** los tres son importables sin errores

#### Scenario: Un cruce horario se rechaza en el servicio sin crear la reserva

- **GIVEN** una reserva aprobada de 10:00 a 12:00 en un espacio y fecha futuros
- **AND** un usuario autenticado que envía una solicitud de 11:00 a 13:00 para el
  mismo espacio y fecha
- **WHEN** la vista de creación procesa el formulario
- **THEN** la respuesta muestra el error de conflicto asociado a la hora de inicio
- **AND** no se crea ninguna reserva y el conteo de `Reserva` no cambia
- **AND** invocar `validar_disponibilidad` del servicio con la misma franja produce el
  mismo error, sin depender de la vista

### Requirement: REQ-BAS-008 Comando seed_data idempotente

El proyecto SHALL incluir el comando `seed_data`, que carga datos de ejemplo de forma
idempotente: ejecutarlo varias veces deja el mismo conjunto, sin duplicados. Su
contrato es la idempotencia y el resumen de la carga, no un conjunto fijo de modelos;
cada cambio posterior define sus propios datos y puede sustituir los provisionales.

#### Scenario: Ejecutar seed_data dos veces no duplica datos

- **GIVEN** una base de datos migrada y sin datos de ejemplo
- **WHEN** se ejecuta `python manage.py seed_data` dos veces consecutivas
- **THEN** ambos comandos terminan sin errores
- **AND** el número de registros de cada modelo sembrado es el mismo tras la primera
  y la segunda ejecución

#### Scenario: Seed_data informa el resultado de la carga

- **GIVEN** una base de datos migrada
- **WHEN** se ejecuta `python manage.py seed_data`
- **THEN** el comando imprime un resumen de los registros creados y actualizados
- **AND** el comando termina con código de salida 0
