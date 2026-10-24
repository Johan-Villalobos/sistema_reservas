# Tasks

## 1. Entorno virtual y dependencias

- [ ] 1.1 Crear el entorno virtual con `python -m venv venv` y activarlo en PowerShell; verificar que `python --version` reporta Python 3.12 o superior y que `venv/` queda creado en la raíz.
- [ ] 1.2 Instalar Django 5.2 LTS con `pip install "Django==5.2.*"` y verificar con `python -m django --version` que la versión instalada es 5.2.x.
- [ ] 1.3 Crear `requirements.txt` con la versión exacta instalada de Django (`Django==5.2.<parche>`); verificar con `pip install -r requirements.txt` que la instalación termina sin errores y que toda línea de dependencia usa `==`.
- [ ] 1.4 Crear `.gitignore` con `db.sqlite3`, `*.sqlite3`, `venv/`, `.venv/`, `__pycache__/`, `*.py[cod]`, `.env`, `staticfiles/`, `media/`, `.coverage`, `htmlcov/`, `.idea/` y `.vscode/`; verificar con `git check-ignore -v db.sqlite3 venv/ modulo.pyc` que las tres rutas aparecen ignoradas.

## 2. Proyecto Django y aplicaciones

- [ ] 2.1 Crear el proyecto en la raíz con `django-admin startproject config .`; verificar que existen `manage.py` y `config/settings.py`, `config/urls.py`, `config/wsgi.py` y `config/asgi.py`.
- [ ] 2.2 Crear las aplicaciones con `python manage.py startapp core`, `startapp accounts`, `startapp spaces` y `startapp reservations`; verificar que cada una contiene `models.py`, `views.py`, `apps.py`, `migrations/` y `tests/`, y que `accounts`, `spaces` y `reservations` incluyen también `services.py`.
- [ ] 2.3 Registrar `core`, `accounts`, `spaces` y `reservations` en `INSTALLED_APPS` de `config/settings.py`; verificar con `python manage.py check` que el comando termina sin errores y sin advertencias de aplicaciones no registradas.
- [ ] 2.4 Crear `accounts/services.py`, `spaces/services.py` y `reservations/services.py` con docstring de módulo y sin lógica de negocio todavía; verificar con `python -c "import accounts.services, spaces.services, reservations.services"` (con el entorno activo y el proyecto en el `sys.path`) que los tres módulos importan sin errores.
- [ ] 2.5 Crear `core/urls.py` con la ruta raíz y enlazarla desde `config/urls.py` con `include("core.urls")`; verificar con `python manage.py check` que no hay errores de enrutamiento y que `reverse("core:home")` resuelve a `/`.
- [ ] 2.6 Implementar `accounts/models.py` con `Usuario(AbstractUser)` mínimo, sin `rol` ni `nombre_completo`, y declarar `AUTH_USER_MODEL = "accounts.Usuario"` en `config/settings.py` antes de generar cualquier migración; verificar con `python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model())"` que imprime `accounts.models.Usuario`.

## 3. Configuración

- [ ] 3.1 Configurar `DATABASES` con `django.db.backends.sqlite3` y `BASE_DIR / "db.sqlite3"`; verificar con `python manage.py diffsettings` que el motor y el nombre de la base son los esperados.
- [ ] 3.2 Configurar `LANGUAGE_CODE = "es-co"`, `TIME_ZONE = "America/Bogota"`, `USE_TZ = True` y `USE_I18N = True`; verificar con `python manage.py diffsettings` que los cuatro valores aparecen.
- [ ] 3.3 Agregar `BASE_DIR / "templates"` a `TEMPLATES["DIRS"]` y `BASE_DIR / "static"` a `STATICFILES_DIRS`; verificar con `python manage.py check` que no hay errores de configuración de plantillas ni de estáticos.
- [ ] 3.4 Escribir `core/tests/test_settings.py` que compruebe motor SQLite, nombre `db.sqlite3`, `America/Bogota`, `USE_TZ` verdadero y `LANGUAGE_CODE == "es-co"`; verificar con `python manage.py test core.tests.test_settings` que las pruebas pasan.
- [ ] 3.5 Generar las migraciones iniciales con `python manage.py makemigrations` y aplicarlas con `python manage.py migrate`; verificar que el comando termina con código 0, que existe `accounts/migrations/0001_initial.py` con el `Usuario` mínimo, que la tabla `accounts_usuario` existe, que `auth_user` no existe y que `db.sqlite3` está en la raíz.

## 4. Plantilla base y página de inicio

- [ ] 4.1 Crear `templates/base.html` con el enlace a Bootstrap 5.3 por CDN (CSS y bundle JS), los bloques `title`, `content` y un contenedor principal; verificar que la plantilla renderiza sin errores de sintaxis abriendo la página de inicio.
- [ ] 4.2 Implementar la barra de navegación en `base.html` con `user.is_authenticated`: enlaces de inicio de sesión y registro para anónimos, y enlaces de espacios, reservas, perfil y cierre de sesión para autenticados; verificar que cada bloque aparece solo en su caso.
- [ ] 4.3 Crear `core/views.py` con la vista de inicio y `templates/core/home.html` que extienda `base.html` y muestre el nombre del sistema; verificar con `python manage.py runserver` que `/` carga sin error 500.
- [ ] 4.4 Escribir `core/tests/test_base_template.py` que renderice `base.html` con `AnonymousUser` y con una instancia de usuario en memoria, y compruebe presencia y ausencia de los enlaces de cada caso; verificar con `python manage.py test core.tests.test_base_template` que las pruebas pasan.

## 5. Comando seed_data

- [ ] 5.1 Crear la estructura `core/management/__init__.py`, `core/management/commands/__init__.py` y `core/management/commands/seed_data.py`; verificar con `python manage.py help seed_data` que el comando aparece registrado.
- [ ] 5.2 Implementar la siembra idempotente de los datos de demostración disponibles en este cambio —los grupos de rol base (`Solicitante`, `Aprobador`, `Administrador`) como conjunto provisional— con `get_or_create` sobre una clave natural, separando la siembra en una función por tipo de dato y con resumen de creados/existentes en la salida; verificar ejecutando `python manage.py seed_data` dos veces y observando que la segunda no crea registros nuevos.
- [ ] 5.3 Escribir `core/tests/test_seed_data.py` que ejecute `call_command("seed_data")` dos veces y compruebe que los conteos del conjunto sembrado no cambian y que no hay duplicados por su clave natural; verificar con `python manage.py test core.tests.test_seed_data` que las pruebas pasan.

## 6. Pruebas de arranque

- [ ] 6.1 Escribir `core/tests/test_home.py` que solicite `/` con el cliente de pruebas y compruebe estado 200 y uso de la plantilla base; verificar con `python manage.py test core.tests.test_home` que la prueba pasa.
- [ ] 6.2 Escribir `core/tests/test_migrations.py` que aplique las migraciones sobre una base SQLite temporal vacía mediante un alias alterno en `override_settings`, compruebe código de salida 0 y ausencia de migraciones pendientes, y cierre las conexiones al limpiar; verificar con `python manage.py test core.tests.test_migrations` que la prueba pasa.
- [ ] 6.3 Ejecutar la suite completa con `python manage.py test` en un entorno recién creado; verificar que todas las pruebas pasan y que no se rompe ningún escenario de la especificación.
- [ ] 6.4 Verificar el flujo de arranque documentado: borrar `db.sqlite3`, ejecutar `python manage.py migrate`, `python manage.py seed_data` y `python manage.py runserver`, y comprobar que la página de inicio responde 200 y que la base de datos sigue sin aparecer en `git status`.

## Workflow follow-up

- Revisar los artefactos del cambio antes de implementar.
- Tras la implementación y las pruebas en verde, archivar el cambio para que la especificación de `base-proyecto` pase a `openspec/specs/`.
- Registrar en el cambio de `accounts` que `accounts/migrations/0001_initial.py` ya crea `accounts.Usuario` y que sus campos de dominio se agregan con una migración nueva, sin regenerar la inicial.
