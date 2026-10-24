# PLAN DE INGENIERIA - Sistema de Gestión de Reservas de Espacios Académicos

Asignatura: Ingeniería de Software
Estudiante: (nombre completo)
Semestre: Octavo
Tecnología base: Django (arquitectura MVT) con base de datos local
Metodología de especificación: SDD con OpenSpec
Versión del documento: 1.0
Estado: Etapa 1 - Planificación (previa a OpenSpec y a la implementación)

---

## 1. Análisis del problema

### 1.1 Identificación de la problemática

La institución gestiona hoy las reservas de laboratorios, auditorios y salas de cómputo mediante correos electrónicos y hojas de cálculo. Esto produce:

- Duplicidad de solicitudes para el mismo espacio y horario.
- Conflictos de horarios que se detectan tarde, muchas veces el mismo día de uso.
- Dificultad para consultar la disponibilidad real de cada espacio.
- Falta de trazabilidad: no hay un historial confiable de quién reservó, quién aprobó y por qué se rechazó.
- Dependencia de personas concretas que concilian manualmente la información.

### 1.2 Necesidades de la institución

| Id | Necesidad | Prioridad |
|----|-----------|-----------|
| N1 | Centralizar el catálogo de espacios y sus características | Alta |
| N2 | Consultar disponibilidad en tiempo real | Alta |
| N3 | Evitar reservas que se crucen en el tiempo | Alta |
| N4 | Controlar quién puede solicitar, aprobar y administrar | Alta |
| N5 | Registrar el flujo de aprobación o rechazo de solicitudes | Alta |
| N6 | Permitir cancelaciones y conservar el historial | Media |
| N7 | Facilitar la administración de usuarios y roles | Media |
| N8 | Preparar el sistema para nuevas reglas de negocio | Media |

### 1.3 Actores involucrados

| Actor | Descripción | Acciones principales |
|-------|-------------|----------------------|
| Solicitante | Docente, estudiante autorizado o personal administrativo | Consultar disponibilidad, crear solicitudes, cancelar sus reservas, ver su historial |
| Aprobador | Coordinador o responsable de espacios | Revisar solicitudes, aprobar o rechazar con justificación |
| Administrador | Responsable del sistema | Gestionar espacios, usuarios, roles y consultar todo el historial |
| Sistema | Aplicación Django | Validar reglas, impedir conflictos, registrar eventos |

### 1.4 Alcance

Dentro del alcance:

- Gestión de espacios académicos (laboratorios, auditorios, salas de cómputo).
- Registro, autenticación y administración de usuarios.
- Roles y permisos (Solicitante, Aprobador, Administrador).
- Creación de solicitudes de reserva.
- Validación de disponibilidad y prevención de reservas simultáneas.
- Aprobación y rechazo de solicitudes.
- Cancelación e historial de reservas.
- Interfaz web con plantillas Django.

### 1.5 Limitaciones y exclusiones

- No se integra con sistemas académicos externos ni con inicio de sesión institucional.
- No se envían correos reales en la primera versión (solo mensajes en pantalla).
- No hay aplicación móvil nativa; la interfaz es web responsiva.
- Se usa una base de datos local (SQLite), por lo que no se contempla alta concurrencia de producción.
- No se incluye pasarela de pagos ni inventario de equipos.
- Las reservas son por franjas de fecha y hora dentro de un mismo día en la primera versión.

### 1.6 Supuestos

- La institución opera en una sola zona horaria (America/Bogota).
- Un espacio solo puede tener una reserva aprobada en un mismo intervalo.
- Las nuevas reglas de negocio pueden llegar durante el desarrollo, por lo que las reglas deben estar aisladas y ser fáciles de modificar.

---

## 2. Propuesta de solución

### 2.1 Descripción general

Aplicación web monolítica construida con Django siguiendo el patrón MVT (Modelo, Vista, Plantilla). Centraliza espacios, usuarios, roles y reservas en una base de datos local gestionada por el ORM de Django. Las reglas de negocio (disponibilidad, solapamiento, transiciones de estado) se concentran en una capa de servicios para que sean verificables y modificables sin tocar las vistas.

### 2.2 Funcionalidades prioritarias

| Orden | Funcionalidad | Justificación |
|-------|---------------|---------------|
| 1 | Autenticación, usuarios y roles | Todo el sistema depende de saber quién actúa |
| 2 | Gestión de espacios | Sin espacios no hay reservas |
| 3 | Creación de solicitudes de reserva | Núcleo del negocio |
| 4 | Validación de disponibilidad y prevención de simultaneidad | Problema principal que resuelve el sistema |
| 5 | Aprobación y rechazo | Completa el flujo de la solicitud |
| 6 | Cancelación e historial | Trazabilidad y cierre del ciclo de vida |
| 7 | Consulta de disponibilidad (calendario o listado) | Mejora de usabilidad |

### 2.3 Organización en módulos (aplicaciones Django)

| Aplicación | Responsabilidad | Modelos principales |
|------------|-----------------|---------------------|
| core | Configuración común, plantilla base, página de inicio, utilidades | Ninguno o abstractos |
| accounts | Usuarios, autenticación, roles y permisos | Usuario personalizado, Rol (o uso de Groups) |
| spaces | Catálogo de espacios académicos | EspacioAcademico, TipoEspacio |
| reservations | Solicitudes, validaciones, aprobación, cancelación e historial | Reserva, HistorialReserva |

Capa de servicios dentro de reservations (archivo services.py): contiene las funciones que aplican las reglas de negocio. Las vistas solo orquestan.

### 2.4 Modelo de datos preliminar

Usuario
- id, username, email, nombre completo, rol, activo.

EspacioAcademico
- id, nombre (único), tipo (LABORATORIO, AUDITORIO, SALA_COMPUTO), capacidad, ubicación, descripción, activo.

Reserva
- id, espacio (clave foránea), solicitante (clave foránea), fecha, hora_inicio, hora_fin, motivo, estado (PENDIENTE, APROBADA, RECHAZADA, CANCELADA), revisado_por (clave foránea opcional), motivo_decision, creado_en, actualizado_en.

HistorialReserva
- id, reserva (clave foránea), estado_anterior, estado_nuevo, actor (clave foránea), fecha_evento, observación.

Restricciones de integridad:
- hora_fin debe ser mayor que hora_inicio (CheckConstraint).
- Un espacio inactivo no admite nuevas solicitudes.
- El estado solo cambia mediante transiciones válidas.

### 2.5 Estados y transiciones de una reserva

- PENDIENTE a APROBADA (solo Aprobador o Administrador).
- PENDIENTE a RECHAZADA (solo Aprobador o Administrador, con motivo).
- PENDIENTE a CANCELADA (solicitante o Administrador).
- APROBADA a CANCELADA (solicitante o Administrador).
- Cualquier otra transición es inválida.

### 2.6 Regla de solapamiento

Dos reservas del mismo espacio y la misma fecha se solapan cuando:

    inicio_A < fin_B  y  fin_A > inicio_B

Solo las reservas en estado APROBADA bloquean el espacio. Al aprobar una solicitud, se vuelve a validar el solapamiento dentro de una transacción atómica para evitar condiciones de carrera.

### 2.7 Estrategia de desarrollo progresivo

Se construye en incrementos verticales, cada uno con su modelo, vista, plantilla, pruebas y migración:

1. Base del proyecto y autenticación.
2. Espacios.
3. Reservas (creación y listado).
4. Disponibilidad y control de conflictos.
5. Aprobación y rechazo.
6. Cancelación e historial.
7. Cambio de negocio solicitado por la institución (Fase 4).
8. Verificación y cierre.

---

## 3. Decisiones de arquitectura y tecnología

### 3.1 Arquitectura seleccionada: MVT en monolito Django

Justificación:
- Es la arquitectura nativa de Django; evita capas artificiales y reduce la complejidad.
- Front, back y base de datos conviven en un único proyecto desplegable, adecuado para un sistema institucional acotado.
- El ORM y el sistema de migraciones facilitan la evolución del esquema.
- Facilita la trazabilidad entre especificaciones, código y pruebas por tener estructura estándar.

Correspondencia MVT:

| Componente MVT | Rol en el proyecto | Ubicación |
|----------------|--------------------|-----------|
| Modelo (Model) | Entidades, relaciones, restricciones y consultas | models.py de cada aplicación |
| Vista (View) | Recibe la petición, invoca servicios, elige respuesta | views.py de cada aplicación |
| Plantilla (Template) | Interfaz HTML renderizada en el servidor | templates y static |
| URLconf | Enrutamiento | urls.py de proyecto y aplicaciones |
| Formularios | Validación de entrada | forms.py |
| Servicios (complemento) | Reglas de negocio reutilizables | services.py |

### 3.2 Stack tecnológico propuesto

| Capa | Tecnología | Nota |
|------|------------|------|
| Lenguaje | Python 3.12 o superior | Versión estable soportada por Django |
| Framework | Django 5.x | Backend y frontend servidos por el mismo framework |
| Frontend | Plantillas Django, HTML5, CSS3, Bootstrap 5 | Interfaz responsiva sin framework JS adicional |
| Base de datos | SQLite 3 (db.sqlite3 local) | Incluida con Django, sin servidor |
| ORM y migraciones | Django ORM y makemigrations/migrate | Versionado del esquema |
| Autenticación | django.contrib.auth con modelo de usuario personalizado | Sesiones y permisos nativos |
| Pruebas | Django TestCase y runner nativo, coverage.py | Pruebas automatizadas |
| Control de versiones | Git | Historial que evidencia la secuencia exigida |
| SDD | OpenSpec | Especificaciones, propuestas, tareas y cambios |
| Entorno | venv y requirements.txt | Reproducibilidad |

### 3.3 Estrategia de persistencia y migración de datos

Persistencia:
- Base de datos local SQLite gestionada por el ORM, configurada en settings.py.
- Archivo db.sqlite3 excluido del repositorio mediante .gitignore.

Migraciones:
- Cada cambio de modelo genera una migración con makemigrations; se versionan en Git dentro de la carpeta migrations de cada aplicación.
- Se define un modelo de usuario personalizado desde la primera migración, porque cambiarlo después es costoso.
- Las migraciones se aplican con migrate en cada incremento.
- Los datos iniciales (roles, tipos de espacio, espacios de ejemplo y usuarios de prueba) se cargan mediante fixtures JSON (loaddata) o un comando de administración propio (seed_data).
- Para el cambio de reglas de negocio de la Fase 4, si se requiere ajustar el esquema, se hará mediante una nueva migración sin alterar las anteriores.
- Respaldo: dumpdata para exportar datos y loaddata para restaurarlos; esto permite migrar los datos a otro motor (por ejemplo PostgreSQL) cambiando solo la configuración de DATABASES.
- Las pruebas usan una base de datos temporal en memoria creada y destruida automáticamente por el runner.

Limitación conocida: SQLite no soporta bloqueo de filas (select_for_update se ignora). Se mitiga con transacciones atómicas, validación previa a la escritura y pruebas específicas de conflicto (ver riesgos).

### 3.4 Organización de componentes (estructura de carpetas)

    reservas_academicas/
      manage.py
      requirements.txt
      README.md
      PLAN_INGENIERIA.md
      INFORME_FINAL.md
      .gitignore
      openspec/
      config/
        settings.py
        urls.py
        wsgi.py
      core/
        templates/core/
        static/
      accounts/
        models.py
        forms.py
        views.py
        urls.py
        templates/accounts/
        tests/
      spaces/
        models.py
        forms.py
        views.py
        urls.py
        templates/spaces/
        tests/
      reservations/
        models.py
        forms.py
        services.py
        views.py
        urls.py
        templates/reservations/
        tests/
      templates/
        base.html

### 3.5 Comparación de decisiones técnicas y alternativas descartadas

| Decisión | Alternativa descartada | Motivo del descarte |
|----------|------------------------|---------------------|
| Monolito Django con MVT | Backend API REST (Django REST Framework) con frontend separado en React | Duplica el esfuerzo, exige manejar dos proyectos y CORS; el enunciado pide front, back y BD dentro del framework |
| SQLite local | PostgreSQL | Requiere instalar y configurar un servidor; no aporta valor en un entorno académico. Queda como migración futura gracias al ORM |
| Plantillas Django con Bootstrap | Frontend SPA con JavaScript | Mayor complejidad y superficie de errores; las plantillas son suficientes para formularios y listados |
| Capa de servicios para reglas de negocio | Lógica dentro de las vistas o dentro de modelos gordos | Las vistas se vuelven difíciles de probar; con servicios las reglas se verifican de forma aislada y el cambio de la Fase 4 afecta un solo lugar |
| Modelo de usuario personalizado con campo de rol | Usar el modelo User por defecto y perfiles separados | Se evita un join adicional y migraciones complicadas posteriores |
| Estados de reserva como campo con opciones (choices) | Tablas separadas por estado | Simplicidad y consultas directas; las transiciones se controlan en servicios |
| Control de concurrencia con transacción atómica y validación | Bloqueo pesimista de filas | SQLite no lo soporta de forma efectiva |

---

## 4. Estrategia de desarrollo

### 4.1 Metodología de trabajo

Enfoque iterativo e incremental con SDD (Spec Driven Development):

1. Plan de ingeniería (este documento) en un commit independiente.
2. Especificaciones en OpenSpec revisadas antes de implementar.
3. Implementación por cambios pequeños, cada uno con su propuesta, tareas y pruebas.
4. Verificación y archivado de cada cambio.

Prácticas:
- Ramas cortas por funcionalidad (por ejemplo feature/espacios) integradas a la rama principal.
- Commits pequeños con mensajes en formato convencional: docs, spec, feat, test, fix, refactor.
- Secuencia obligatoria visible en Git: commit del plan, luego commits de especificaciones, luego commits de código.
- Revisión personal de cada cambio antes de integrarlo (lista de verificación).

### 4.2 Etapas de implementación

| Etapa | Contenido | Entregable |
|-------|-----------|------------|
| E0 | Plan de ingeniería | PLAN_INGENIERIA.md |
| E1 | Inicialización de OpenSpec y especificaciones | Directorio openspec con especificaciones y tareas |
| E2 | Revisión de especificaciones | Registro de ambigüedades y correcciones |
| E3 | Proyecto base, usuarios y roles | Proyecto Django, accounts, migraciones iniciales |
| E4 | Espacios | App spaces con CRUD |
| E5 | Reservas, disponibilidad y simultaneidad | App reservations, servicios y pruebas |
| E6 | Aprobación, rechazo, cancelación e historial | Flujo completo de estados |
| E7 | Gestión de cambios (nueva regla de negocio) | Propuesta, delta de especificación, código, pruebas |
| E8 | Verificación y cierre | README.md, INFORME_FINAL.md |

### 4.3 Orden de desarrollo y dependencias

    accounts (usuarios y roles)
        -> spaces (requiere usuarios con rol Administrador)
            -> reservations (requiere usuarios y espacios)
                -> disponibilidad y simultaneidad (requiere reservas)
                    -> aprobación y rechazo (requiere reservas y roles)
                        -> cancelación e historial (requiere estados)

Dependencias transversales:
- La plantilla base y la navegación dependen de la autenticación.
- Las pruebas de cada módulo dependen de fixtures o fábricas de datos de los módulos anteriores.
- El cambio de la Fase 4 depende de que servicios.py ya concentre las validaciones.

### 4.4 Criterios de terminado (Definition of Done)

Una etapa se considera terminada cuando:

- La especificación correspondiente fue revisada y no tiene ambigüedades abiertas.
- El código implementa los escenarios de aceptación de la especificación.
- Las pruebas automatizadas de la etapa pasan.
- Las migraciones se generan y se aplican sin errores en una base de datos limpia.
- No se rompen pruebas de etapas anteriores.
- Los cambios están registrados en commits con mensajes claros.
- Las tareas de OpenSpec correspondientes están marcadas como completadas.

---

## 5. Estrategia de calidad

### 5.1 Tipos de pruebas

| Tipo | Objetivo | Herramienta |
|------|----------|-------------|
| Pruebas unitarias de modelos | Restricciones, estados, validaciones de campos | Django TestCase |
| Pruebas unitarias de servicios | Solapamiento, transiciones, reglas de negocio | Django TestCase |
| Pruebas de vistas y formularios | Respuestas, redirecciones, mensajes, validaciones | Django test Client |
| Pruebas de permisos | Acceso según rol | Django test Client |
| Pruebas de integración | Flujo completo: solicitar, aprobar, cancelar | Django TestCase |
| Pruebas de regresión | Confirmar que un cambio no afecta lo existente | Suite completa |
| Pruebas de migración | Aplicar migraciones en base limpia | migrate sobre base temporal |
| Cobertura | Medir porcentaje de código ejercitado (meta mínima 80 por ciento en servicios y modelos) | coverage.py |
| Verificación manual guiada | Recorrido de la interfaz según escenarios | Lista de verificación |

### 5.2 Riesgos identificados y mitigación

| Id | Riesgo | Probabilidad | Impacto | Estrategia de mitigación |
|----|--------|--------------|---------|--------------------------|
| R1 | Reservas simultáneas o solapadas por condiciones de carrera | Media | Alto | Validación dentro de transacción atómica, revalidación al aprobar, pruebas específicas de conflicto |
| R2 | La IA genera código que no corresponde a la especificación | Alta | Alto | Prompts basados en las especificaciones, revisión línea por línea, pruebas derivadas de los escenarios |
| R3 | Especificaciones ambiguas o contradictorias | Media | Alto | Fase de revisión obligatoria y comparación contra este plan |
| R4 | Errores de zona horaria o manejo de fechas | Media | Medio | Configurar TIME_ZONE y USE_TZ, pruebas con límites de horario |
| R5 | Fallos en migraciones o pérdida de datos | Baja | Alto | Migraciones versionadas, respaldo con dumpdata antes de cambios de esquema, pruebas en base limpia |
| R6 | Cambios de requisitos tardíos (nueva regla de negocio) | Alta | Medio | Reglas aisladas en services.py, gestión del cambio mediante OpenSpec |
| R7 | Permisos mal aplicados que exponen acciones indebidas | Media | Alto | Decoradores y mixins centralizados, pruebas de acceso por rol |
| R8 | Limitaciones de SQLite en concurrencia | Media | Medio | Documentar la limitación y facilitar migración a otro motor |
| R9 | Pérdida de trazabilidad entre requisitos, código y pruebas | Media | Medio | Identificadores de requisito referenciados en pruebas y commits |
| R10 | Falta de tiempo por acumulación de tareas | Media | Medio | Priorización por incrementos y alcance acotado |

### 5.3 Mecanismos de verificación del cumplimiento de requisitos

- Matriz de trazabilidad: cada requisito de OpenSpec tiene un identificador, el archivo de código que lo implementa y las pruebas que lo verifican.
- Cada escenario de aceptación (formato dado, cuando, entonces) se convierte en al menos una prueba automatizada.
- Los nombres de las pruebas incluyen el identificador del requisito.
- Se ejecuta la suite completa antes de cada integración y antes del cierre.
- Revisión final cruzada: especificaciones contra código y contra este plan.
- Uso de la validación de OpenSpec para comprobar la consistencia de especificaciones y cambios.

Ejemplo de trazabilidad:

| Requisito | Escenario | Código | Prueba |
|-----------|-----------|--------|--------|
| REQ-RES-004 Prevención de simultaneidad | Solicitud que se cruza con reserva aprobada es rechazada | reservations/services.py | test_services.py, test_overlap |

---

## 6. Uso de SDD e inteligencia artificial

### 6.1 Cómo se utilizará OpenSpec

- Inicializar OpenSpec en el repositorio después del commit del plan.
- Definir las especificaciones base por capacidad: espacios, usuarios, roles y permisos, solicitudes, disponibilidad, simultaneidad, aprobación y rechazo, cancelación e historial.
- Cada cambio se gestiona como una propuesta con su descripción, diseño si aplica, deltas de especificación y lista de tareas.
- Al completar un cambio, se verifica y se archiva para que las especificaciones vigentes reflejen el estado real del sistema.
- La nueva regla de negocio de la Fase 4 se tramita exclusivamente como un cambio de OpenSpec antes de tocar el código.

### 6.2 Cómo se transforma el plan en especificaciones

1. Cada funcionalidad prioritaria del apartado 2.2 se convierte en una capacidad de OpenSpec.
2. Cada necesidad (N1 a N8) se traduce en requisitos con lenguaje verificable (el sistema debe...).
3. Las restricciones del modelo de datos y de estados (apartados 2.4 a 2.6) se convierten en requisitos y escenarios.
4. Cada requisito incluye escenarios de aceptación en formato dado, cuando, entonces.
5. Las tareas de implementación se derivan del orden de desarrollo del apartado 4.3.
6. Se verifica la correspondencia mediante una revisión cruzada plan contra especificaciones.

### 6.3 Actividades que se delegarán a la IA

- Generar el esqueleto del proyecto Django y las aplicaciones.
- Redactar borradores de modelos, formularios, vistas y plantillas según las especificaciones.
- Proponer pruebas a partir de los escenarios de aceptación.
- Sugerir mejoras de redacción en especificaciones, que luego se validan.
- Generar datos de ejemplo (fixtures).
- Apoyar la documentación (README e informe) con revisión posterior.

### 6.4 Cómo se verificará el código generado

- Lectura y revisión de todo el código antes de confirmarlo en Git.
- Comparación contra las especificaciones y contra la arquitectura definida (MVT y capa de servicios).
- Ejecución de la suite de pruebas y análisis de cobertura.
- Revisión de migraciones generadas antes de aplicarlas.
- Pruebas manuales de los escenarios principales.
- Rechazo de código que añada funcionalidades no especificadas.
- Uso de instrucciones acotadas a una tarea de OpenSpec a la vez para limitar el alcance de la IA.

### 6.5 Decisiones que son responsabilidad del estudiante

- Arquitectura, stack y estrategia de persistencia.
- Alcance, prioridades y orden de desarrollo.
- Redacción final y aprobación de las especificaciones.
- Reglas de negocio, estados y permisos.
- Aceptación o rechazo del código generado.
- Gestión de riesgos y decisiones de cambio.
- Contenido del informe final y la sustentación del sistema.

---

## 7. Control de versiones y secuencia de entrega

| Orden | Commit esperado | Contenido |
|-------|-----------------|-----------|
| 1 | docs: agregar plan de ingenieria | Solo PLAN_INGENIERIA.md |
| 2 | chore: inicializar OpenSpec | Estructura de OpenSpec |
| 3 | spec: especificaciones iniciales | Capacidades y escenarios |
| 4 | spec: revision de especificaciones | Correcciones y tareas |
| 5 en adelante | feat y test por incremento | Código y pruebas |
| Fase 4 | spec y luego feat | Propuesta del cambio, después implementación |
| Cierre | docs: README e informe final | README.md e INFORME_FINAL.md |

Entregables finales del repositorio: PLAN_INGENIERIA.md, directorio de OpenSpec, código fuente, pruebas automatizadas, README.md e INFORME_FINAL.md.

---

## 8. Registro de cambios del documento

| Versión | Descripción |
|---------|-------------|
| 1.0 | Versión inicial previa a las especificaciones |

Las decisiones que cambien durante el desarrollo se registrarán en INFORME_FINAL.md, conservando este documento como evidencia de la planificación original.
