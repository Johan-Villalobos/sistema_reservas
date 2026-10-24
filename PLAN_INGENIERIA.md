# PLAN DE INGENIERIA DE SOFTWARE
## Sistema de Gestión de Reservas de Espacios Académicos

**Autor:** Estudiante de Ingeniería en Desarrollo de Software (8vo Semestre)
**Fecha:** Octubre 2026

---

## 1. Análisis del problema

### Identificación de la problemática
Actualmente, la institución educativa gestiona las reservas de sus espacios académicos (laboratorios, auditorios y salas de cómputo) de forma manual utilizando correos electrónicos y hojas de cálculo. Este enfoque artesanal provoca:
*   Duplicidad en las solicitudes de reserva.
*   Conflictos de horarios (doble asignación de un mismo espacio).
*   Falta de visibilidad y dificultad para que los usuarios consulten la disponibilidad en tiempo real.
*   Retrasos en la aprobación y gestión por parte de los administradores.

### Necesidades de la institución
La institución necesita un sistema centralizado, automatizado y confiable que elimine los cuellos de botella del proceso actual. Se requiere que el sistema valide la disponibilidad automáticamente, notifique sobre el estado de las solicitudes y mantenga un historial auditable.

### Actores involucrados
*   **Solicitantes (Docentes/Estudiantes):** Usuarios que consultan disponibilidad, crean solicitudes de reserva, y cancelan sus propias reservas.
*   **Administradores de Espacios:** Personal encargado de revisar, aprobar o rechazar las solicitudes, así como de administrar el catálogo de espacios.
*   **Administrador del Sistema:** Encargado de gestionar los roles, permisos y configuraciones globales.

### Alcance y limitaciones del sistema
*   **Alcance:** El sistema abarcará el registro de usuarios, catálogo de espacios, calendario de disponibilidad, motor de reglas para reservas (evitar choques de horarios, límite de horas) y flujos de aprobación.
*   **Limitaciones:** El sistema no controlará el acceso físico a los espacios (ej. cerraduras inteligentes) ni manejará cobros o facturación. Estará limitado a la red y comunidad académica de la institución.

---

## 2. Propuesta de solución

### Descripción general
Se propone desarrollar una aplicación web transaccional utilizando el framework Django. La solución centralizará la información en una base de datos relacional, ofreciendo interfaces claras para que los solicitantes autogestionen sus reservas y los administradores moderen el uso de los espacios.

### Funcionalidades prioritarias
1.  **Autenticación y Autorización:** Login y gestión de roles (Admin, Solicitante).
2.  **Gestión de Espacios (CRUD):** Creación, lectura, actualización y eliminación de laboratorios, salas y auditorios.
3.  **Motor de Reservas:** Creación de solicitudes con validación estricta de cruces de horarios.
4.  **Panel de Aprobaciones:** Interfaz para que los administradores aprueben o rechacen solicitudes pendientes.
5.  **Historial y Cancelaciones:** Visualización del estado de las reservas y opción de cancelación anticipada.

### Organización del sistema en módulos
*   `modulo_usuarios`: Gestión de perfiles, autenticación y permisos.
*   `modulo_espacios`: Catálogo de recursos físicos y sus características (capacidad, equipos).
*   `modulo_reservas`: Lógica principal de negocio, solicitudes, validaciones de tiempo e historial.

### Estrategia de desarrollo progresivo
Se utilizará un enfoque iterativo. Primero se definirá el modelo de datos y las migraciones base. Luego se desarrollará la lógica del backend (validaciones de disponibilidad) y, finalmente, se integrarán las vistas y plantillas (frontend) para que los usuarios interactúen con el sistema.

---

## 3. Decisiones de arquitectura y tecnología

### Arquitectura seleccionada y justificación
Se seleccionó la arquitectura **MVT (Model-View-Template)** nativa del framework Django. 
*Justificación:* Al ser un proyecto que requiere una base de datos robusta, reglas de negocio claras y paneles de administración, MVT permite a un solo desarrollador full-stack avanzar rápidamente. Django ya acopla el backend y el frontend, evitando la sobrecarga de configurar una API REST y una aplicación SPA separada, lo cual reduce la complejidad y acelera el desarrollo iterativo.

### Stack tecnológico propuesto
*   **Backend y Lógica:** Python 3 con Django.
*   **Frontend:** HTML5, CSS3, JavaScript básico y Bootstrap (para diseño responsivo y rápido en las plantillas).
*   **Base de datos local:** SQLite (integrada en Django por defecto, ideal para la fase de desarrollo y pruebas de concepto requeridas en esta etapa).

### Estrategia de persistencia de datos
Se utilizará el ORM de Django. Toda modificación estructural de la base de datos se gestionará a través del sistema de **migraciones** de Django (`makemigrations` y `migrate`). Esto garantiza la trazabilidad de los cambios en la base de datos a lo largo del desarrollo y facilita el control de versiones.

### Organización de componentes
El proyecto se dividirá en aplicaciones (apps) de Django altamente cohesivas y poco acopladas: `core` (vistas genéricas), `users` (usuarios extendidos), `spaces` (modelos de espacios), `reservations` (lógica de asignación).

### Comparación de decisiones técnicas vs alternativas
1.  **Arquitectura: MVT (Django) vs. API REST (Node.js) + React.**
    *   *Decisión:* MVT (Django).
    *   *Razón:* Un enfoque desacoplado (React+Node) aumentaría la complejidad del proyecto y los tiempos de configuración. Django incluye panel de administración y ORM "out of the box", alineándose mejor con los tiempos de entrega.
2.  **Base de datos: SQLite local vs. PostgreSQL en la nube.**
    *   *Decisión:* SQLite local.
    *   *Razón:* Para cumplir con la actividad y facilitar la evaluación, una BD local embebida elimina la necesidad de credenciales externas o servicios en la nube. El ORM permite migrar a Postgres en producción sin cambiar el código de negocio.
3.  **Frontend: Plantillas de Django + Bootstrap vs. Tailwind CSS.**
    *   *Decisión:* Bootstrap.
    *   *Razón:* Tailwind requiere un proceso de construcción (build process) que interfiere con la simplicidad de los templates directos de Django. Bootstrap permite prototipar interfaces funcionales mediante clases predefinidas sin configuración adicional.

---

## 4. Estrategia de desarrollo

### Metodología de trabajo
Desarrollo guiado por especificaciones (Specification-Driven Development - SDD) junto con iteraciones ágiles cortas. No se programará ninguna línea de código sin que su especificación haya sido validada en OpenSpec.

### Etapas de implementación
1.  **Fase de Especificación:** Redacción formal de requisitos en OpenSpec.
2.  **Infraestructura Base:** Inicialización de Django, configuración de base de datos local y migraciones iniciales.
3.  **Desarrollo de Modelos:** Creación de las clases en el ORM (Usuarios, Espacios, Reservas).
4.  **Lógica de Negocio (Views):** Implementación de validaciones (ej. no reservas simultáneas).
5.  **Interfaz de Usuario (Templates):** Integración visual.
6.  **Gestión de Cambios:** Incorporación de la regla de las "cuatro horas" modificando primero las especificaciones.

### Dependencias entre componentes
El módulo de `reservas` depende inherentemente de `usuarios` y `espacios`. Por lo tanto, el orden estricto de desarrollo será: Configuración Core -> Usuarios -> Espacios -> Reservas -> Pruebas de integración.

### Criterios para considerar terminada cada etapa
*   Las especificaciones en OpenSpec están aprobadas y sin ambigüedades.
*   El código pasa las pruebas unitarias.
*   Las migraciones de la base de datos se ejecutan sin errores.
*   La interfaz permite ejecutar el caso de uso de extremo a extremo.

---

## 5. Estrategia de calidad

### Tipos de pruebas
*   **Pruebas Unitarias:** Para verificar el comportamiento individual de los modelos y sus validaciones (ej. probar que el ORM levanta un error si hay choque de horarios). Se usará `django.test.TestCase`.
*   **Pruebas de Integración:** Para validar el flujo completo desde que un usuario envía el formulario de reserva hasta que el administrador lo aprueba.

### Riesgos y mitigación
1.  **Riesgo:** Condiciones de carrera (dos usuarios reservando el mismo espacio al mismo exacto tiempo).
    *   *Mitigación:* Uso de transacciones atómicas (`transaction.atomic`) y bloqueos a nivel de base de datos (`select_for_update`) en Django.
2.  **Riesgo:** Desviación entre el código generado por IA y las especificaciones.
    *   *Mitigación:* Revisión manual estricta del código sugerido y ejecución de pruebas antes de cada commit.
3.  **Riesgo:** Pérdida de datos durante modificaciones al modelo.
    *   *Mitigación:* Crear y probar los archivos de migración localmente antes de aplicarlos.
4.  **Riesgo:** Ambigüedad en la definición de "choque de horarios".
    *   *Mitigación:* Especificar matemáticamente las reglas de superposición de tiempo en OpenSpec.
5.  **Riesgo:** Vulnerabilidades de seguridad (Inyección SQL, XSS).
    *   *Mitigación:* Uso exclusivo del ORM de Django y su motor de plantillas que auto-escapa caracteres por defecto.

### Verificación de requisitos
Se crearán escenarios de aceptación en OpenSpec con formato Gherkin (Dado/Cuando/Entonces). Cada escenario tendrá su contraparte en los tests automatizados de Django.

---

## 6. Uso de SDD e Inteligencia Artificial

### ¿Cómo se utilizará OpenSpec?
OpenSpec será la única fuente de verdad. Antes de crear vistas o modelos en Django, se documentarán los criterios de aceptación, precondiciones y flujos en OpenSpec. Cuando surja el cambio de la regla de "cuatro horas", se actualizará OpenSpec primero.

### ¿Cómo se transformará el plan en especificaciones?
Este plan (secciones 1 y 2) se desglosará en Historias de Usuario formales. Por ejemplo, "Gestión de solicitudes" se traducirá en especificaciones de comportamiento (BDD) que definirán las entradas exactas y salidas esperadas.

### ¿Qué actividades se delegarán a la IA?
*   Generación de código "boilerplate" (estructuras base de modelos, vistas genéricas y formularios de Django).
*   Maquetación HTML/CSS con Bootstrap a partir de descripciones funcionales.
*   Generación de plantillas de pruebas unitarias basadas en los criterios de OpenSpec.

### ¿Cómo se verificará el código generado?
*   Revisión de sintaxis y arquitectura (que respete el patrón MVT).
*   Ejecución local del servidor (`python manage.py runserver`) para validación visual.
*   Ejecución de la suite de pruebas (`python manage.py test`) para comprobar que el código de la IA cumple con OpenSpec.

### ¿Qué decisiones serán responsabilidad del estudiante?
*   La definición estricta de las reglas de negocio en el ORM (ej. la lógica transaccional de reservas).
*   La estructuración y aplicación de las migraciones de la base de datos (para evitar corrupción de datos locales).
*   La decisión de cuándo y cómo integrar el cambio de alcance (Fase 4), analizando el impacto en la base de datos y la arquitectura antes de pedirle a la IA que modifique el código.