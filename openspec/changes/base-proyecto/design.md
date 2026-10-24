# Design

## Context

Ver `proposal.md` — Why. El repositorio contiene únicamente `PLAN_INGENIERIA.md`, la
estructura vacía de `openspec/` y un directorio `venv/` local. No hay `manage.py`,
ni paquete de configuración, ni aplicaciones Django, ni plantilla base, ni pruebas.
El plan de ingeniería (apartados 2.3, 3.4 y 4.3) fija la arquitectura MVT, las
cuatro aplicaciones y el orden de construcción; este diseño aterriza esa
planificación en la estructura real del repositorio, cuya raíz es
`Proyecto SDD/` (no existe la carpeta contenedora `reservas_academicas/` del
diagrama del plan; los elementos se ubican directamente en la raíz del repositorio).

Restricciones relevantes:

- Entorno Windows con `venv`; comandos de activación en PowerShell.
- Base de datos SQLite local, sin servidor, excluida de Git.
- Este cambio solo define el usuario mínimo necesario para fijar `AUTH_USER_MODEL`;
  los campos de dominio (`rol`, nombre completo y unicidad de correo) y los modelos de
  espacios y reservas llegan con `accounts`, `spaces` y `reservations`.
- Las reglas de negocio deben quedar aisladas desde el inicio, en el módulo
  `services.py` de cada aplicación de dominio, para el cambio de negocio de la Fase 4.

## Goals / Non-Goals

**Goals:**

- Dejar un proyecto Django arrancable y verificable con `check`, `migrate` y la
  suite de pruebas en verde.
- Fijar las convenciones que heredarán los tres cambios siguientes: ubicación de
  plantillas, rutas, un módulo `services.py` por aplicación y comando de datos de
  ejemplo.
- Resolver de forma explícita cómo se fijan el modelo de usuario inicial y
  `AUTH_USER_MODEL` antes de la primera migración, sin publicar una tabla de
  `auth.User` que luego haya que descartar.

**Non-Goals:**

- No se completan los campos de dominio del usuario —`rol`, `nombre_completo` y la
  unicidad insensible a mayúsculas del correo—, ni se implementan roles, formularios o
  vistas de cuentas; corresponden a `usuarios-roles-permisos`.
- No se implementan modelos de espacios o reservas (corresponden a `spaces` y
  `reservations`).
- No se implementan formularios, vistas de negocio, permisos por rol ni el flujo de
  aprobación.
- No se configura despliegue, servidor WSGI/ASGI de producción, archivos estáticos
  recolectados ni base de datos distinta de SQLite.
- No se define la política de cobertura ni CI; se abordan en cambios posteriores.

## Decisions

### 1. Distribución del proyecto en la raíz del repositorio

Se crea `manage.py` en la raíz de `Proyecto SDD/` y el paquete `config/`
(`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`). Las aplicaciones `core`,
`accounts`, `spaces` y `reservations` se crean como paquetes hermanos en la raíz,
no dentro de `config/`.

- **Motivo**: `startproject` con destino `.` produce exactamente esta distribución,
  mantiene las rutas de importación cortas (`accounts.views`) y coincide con el
  diagrama 3.4 del plan.
- **Alternativa descartada**: anidar todo en `reservas_academicas/`. Obligaría a un
  nivel extra de directorios sin aportar aislamiento, y el repositorio ya es la
  raíz del proyecto.
- **Alternativa descartada**: apps dentro de un paquete `apps/`. Añade indirección
  y no la exige el plan.

Cada aplicación se crea con `startapp` y se registra en `INSTALLED_APPS`. Las
aplicaciones `accounts`, `spaces` y `reservations` nacen con la estructura estándar
(`models.py`, `views.py`, `urls.py`, `templates/`, `tests/`) para que los cambios
posteriores solo agreguen contenido. En este cambio se crean además
`accounts/services.py`, `spaces/services.py` y `reservations/services.py` únicamente
con el docstring de módulo y sin funciones de negocio, dejando el punto de extensión
reservado para cada aplicación (REQ-BAS-007).

### 2. Plantilla base global en `templates/base.html`

`BASE_DIR / "templates"` se agrega a `TEMPLATES["DIRS"]`. `base.html` vive en la
raíz de `templates/`, no dentro de una aplicación, porque la comparten todas.

- **Motivo**: la plantilla base es transversal; ubicarla en `core/templates/`
  obligaría a que toda app dependiera de `core`.
- **Decisión relacionada**: `core` aporta `templates/core/home.html`, que extiende
  `base.html`, y la vista de la ruta `/`.

La navegación se implementa con el contexto estándar de Django
(`django.contrib.auth.context_processors.auth`), usando `user.is_authenticated`:

- Anónimo: enlaces a inicio de sesión (`/accounts/login/`), registro y la marca
  del sitio.
- Autenticado: enlaces a espacios, reservas, perfil y cierre de sesión
  (`/accounts/logout/`).

Las rutas de cuentas pueden no existir todavía; en este cambio los enlaces se
declaran como texto con `href` a rutas reservadas y las pruebas de plantilla
verifican la presencia/ausencia de los enlaces, no que las rutas respondan. Cuando
`accounts` implemente sus `urls.py`, los `href` quedarán activos sin tocar
`base.html` salvo ajustes de nombres de ruta.

### 3. Bootstrap 5 por CDN con versión fija

`base.html` enlaza Bootstrap 5.3.x (CSS y bundle JS) desde jsDelivr, con `integrity`
y `crossorigin` cuando el CDN los publique.

- **Motivo**: cero herramientas de build, coherente con "plantillas Django +
  Bootstrap" del plan (3.2), y mantiene el repositorio liviano.
- **Alternativa descartada**: vendorizar Bootstrap en `static/`. Añade ~300 KB
  binarios versionados y no se requiere para el alcance académico.
- **Trade-off**: la interfaz depende de conectividad en la demostración. Se
  mitiga permitiendo que la página siga siendo legible sin CSS y documentando el
  CDN en el README del cambio posterior. Si el docente exige funcionamiento
  offline, se cambia a vendorizado sin afectar requisitos.

### 4. Configuración regional y de base de datos explícita en `config/settings.py`

`DATABASES` con `django.db.backends.sqlite3` y `BASE_DIR / "db.sqlite3"`;
`LANGUAGE_CODE = "es-co"`, `TIME_ZONE = "America/Bogota"`, `USE_TZ = True`,
`USE_I18N = True`. `DEBUG` y `SECRET_KEY` quedan como valores de desarrollo local
con advertencia de no usar en producción; no se introduce `django-environ` en este
cambio para no sumar dependencias.

- **Motivo**: REQ-BAS-002 exige esos valores exactos; `USE_TZ` activo evita
  ambigüedad en las futuras validaciones de franjas horarias (riesgo R4 del plan).
- **Alternativa descartada**: `TIME_ZONE = "UTC"` con conversión en plantillas. El
  sistema es de una sola zona (supuesto 1.6) y la conversión manual agrega puntos
  de fallo.

### 5. Usuario mínimo y `AUTH_USER_MODEL` desde la primera migración

`accounts/models.py` define en este cambio un `Usuario(AbstractUser)` mínimo, sin
campos de dominio adicionales, y `config/settings.py` declara
`AUTH_USER_MODEL = "accounts.Usuario"` **antes** de ejecutar la primera migración del
proyecto. `accounts/migrations/0001_initial.py` se genera y se versiona en este
cambio; `usuarios-roles-permisos` la conserva y agrega los campos de dominio con una
migración nueva (`0002`), sin regenerar la inicial.

- **Motivo**: el plan 3.3 exige definir el usuario personalizado desde la primera
  migración porque cambiarlo después es costoso y deja el esquema inconsistente. Al
  fijarlo en `base-proyecto`, la base de desarrollo nace con `accounts_usuario` y
  nunca se crea ni se descarta `auth_user`.
- **Alcance mínimo**: `AbstractUser` aporta `username`, `email`, `password`,
  `is_active`, `is_staff` y el gestor de usuarios. No se agregan `rol`,
  `nombre_completo` ni la restricción de correo único; esas decisiones pertenecen a
  `usuarios-roles-permisos` y llegarían con una migración posterior.
- **Sin reinicio destructivo**: como la migración inicial ya apunta al modelo
  personalizado, `usuarios-roles-permisos` no necesita borrar `db.sqlite3` para
  cambiar `AUTH_USER_MODEL`; solo aplica su migración incremental. El borrado de la
  base queda como recurso de desarrollo, no como paso obligatorio del cambio.
- **Alternativa descartada**: mantener `auth.User` en `base-proyecto` y cambiarlo en
  `accounts`. Publica una migración inicial que luego se descarta y contradice
  REQ-USR-001 y el plan 3.3.
- **Cómo se prueban los escenarios de navegación sin cuentas completas**: las pruebas
  de plantilla renderizan `base.html` con un `AnonymousUser` y con una instancia de
  `Usuario` en memoria (sin guardarla), de modo que no se depende de login ni de los
  campos de dominio. La prueba de la página de inicio usa el cliente de pruebas sin
  autenticación.

### 6. `seed_data` en `core`, idempotente por clave natural

`core/management/commands/seed_data.py` siembra los datos de demostración disponibles
en este cambio —los grupos de rol base (`Solicitante`, `Aprobador`, `Administrador`)
como conjunto provisional— con `get_or_create` sobre una clave natural y reporta
cuántos creó y cuántos ya existían. El requisito no fija `Group` como contrato: el
cambio `usuarios-roles-permisos` sustituirá esta siembra por usuarios y declarará
`base-proyecto` como capacidad modificada.

- **Motivo**: `core` es la aplicación de utilidades comunes y los grupos son el
  único dato de ejemplo disponible sin modelos de dominio. `get_or_create` sobre una
  clave única natural garantiza la idempotencia de REQ-BAS-008 sin estado auxiliar.
- **Alternativa descartada**: fixtures JSON con `loaddata`. No son idempotentes por
  sí mismos (los `pk` fijos fallan o sobrescriben) y el plan permite explícitamente
  un comando propio.
- **Alternativa descartada**: sembrar espacios y reservas de demostración ahora.
  Requiere modelos que no existen en este cambio; se ampliará en `spaces` y
  `reservations` reutilizando el mismo comando.
- **Trade-off**: los grupos son datos provisionales. `usuarios-roles-permisos` los
  reemplaza por usuarios y `gestion-espacios` agrega espacios; cada sustitución
  conserva la idempotencia y se registra como capacidad modificada.

### 7. Pruebas de arranque en `core/tests/`

- `test_home.py`: la ruta `/` responde 200 y usa `base.html`; la plantilla muestra
  enlaces de anónimo y de autenticado según corresponda.
- `test_migrations.py`: aplica las migraciones sobre una base SQLite temporal y
  vacía usando un alias de base de datos alterno en `override_settings`, y verifica
  que no queden migraciones pendientes (`showmigrations --plan` sin filas `[ ]`), que
  exista `accounts_usuario` y que no exista `auth_user`.
- `test_seed_data.py`: ejecuta `call_command("seed_data")` dos veces y compara
  conteos del conjunto sembrado.
- `test_settings.py`: comprueba motor, nombre de base, `TIME_ZONE`, `USE_TZ`,
  `LANGUAGE_CODE` y que `AUTH_USER_MODEL` sea `"accounts.Usuario"`.

- **Motivo**: los escenarios de REQ-BAS-002/004/005/008 son verificables sin
  interacción manual; ejecutar `migrate` en una base temporal cubre el criterio de
  "base limpia" sin destruir la base de desarrollo.
- **Alternativa descartada**: probar el comando `migrate` solo manualmente. El plan
  (5.1) exige prueba de migración automatizada.

### 8. Dependencias y versionado

`requirements.txt` fija `Django==5.2.<parche>` (LTS 5.2, parche más reciente al
implementar) con `==`. No se agregan dependencias de terceros en este cambio.

- **Motivo**: REQ-BAS-006; Django 5.2 LTS es la versión 5.x con soporte extendido
  y compatible con Python 3.12.
- **Alternativa descartada**: rango `Django>=5,<6`. Rompe la reproducibilidad que
  exige el requisito.

`.gitignore` incluye: `db.sqlite3`, `*.sqlite3`, `venv/`, `.venv/`, `__pycache__/`,
`*.py[cod]`, `.env`, `staticfiles/`, `media/`, `.coverage`, `htmlcov/`, `.idea/`,
`.vscode/`.

## Risks / Trade-offs

- **Migración inicial de `accounts` compartida entre dos cambios** → `base-proyecto`
  crea `0001_initial` con el `Usuario` mínimo y `usuarios-roles-permisos` debe
  agregar sus campos con `0002`, sin editar ni regenerar `0001`. Se registra como
  dependencia explícita en las tareas de ambos cambios.
- **`seed_data` con datos provisionales** → `usuarios-roles-permisos` sustituye los
  grupos por usuarios y `gestion-espacios` agrega espacios; el comando se escribe con
  una función por tipo de dato y el requisito solo exige idempotencia, no un modelo
  concreto.
- **Dependencia del CDN de Bootstrap** → la página mantiene estructura semántica sin
  CSS; se documenta la alternativa vendorizada y se puede cambiar sin tocar
  requisitos.
- **Prueba de migración sobre base temporal en Windows** → los archivos SQLite
  temporales deben cerrarse antes de borrarse; se usa `tempfile.TemporaryDirectory`
  y `connections.close_all()` en la limpieza.
- **Enlaces de navegación a rutas aún inexistentes** → no se enlazan con `{% url %}`
  en este cambio para no romper el render; al implementarse `accounts` se migran a
  rutas nombradas. Riesgo de enlaces muertos temporal, aceptado y acotado a un
  cambio.
- **`DEBUG=True` y `SECRET_KEY` de desarrollo** → aceptado para entorno local
  académico; se anota en `settings.py` y en el README final que deben externalizarse
  antes de cualquier despliegue.

## Migration Plan

1. Crear y activar el entorno virtual; instalar Django y congelar la versión en
   `requirements.txt`.
2. Crear el proyecto en la raíz y las cuatro aplicaciones; registrar en
   `INSTALLED_APPS`.
3. Ajustar `config/settings.py` (SQLite, `es-co`, `America/Bogota`, `USE_TZ`,
   `AUTH_USER_MODEL`, rutas de plantillas y estáticos), `config/urls.py` y
   `core/urls.py`.
4. Crear `templates/base.html` y `templates/core/home.html` con Bootstrap 5 y la
   navegación condicionada por autenticación.
5. Crear `accounts/models.py` con el `Usuario(AbstractUser)` mínimo,
   `accounts/services.py`, `spaces/services.py`, `reservations/services.py` y
   `core/management/commands/seed_data.py`.
6. Generar `accounts/migrations/0001_initial.py` y las migraciones iniciales del
   resto del proyecto; aplicar `migrate` sobre la base local y ejecutar la suite de
   arranque.
7. Verificar `.gitignore` con `git check-ignore` y confirmar que `db.sqlite3` no
   aparece en `git status`.

**Rollback**: al no existir datos de producción ni migraciones de negocio, revertir
consiste en eliminar el commit del cambio y borrar `db.sqlite3`; no hay pérdida de
información relevante.

## Open Questions

Ninguna que afecte las especificaciones, el enfoque o el desglose de tareas. La
versión exacta del parche de Django y de Bootstrap se fija al implementar, dentro
de las líneas mayores ya decididas.
