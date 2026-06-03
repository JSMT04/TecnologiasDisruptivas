# 📋 Historial de Cambios (Changelog) — FlowStep AI

Este archivo documenta los hitos y optimizaciones de las fases más recientes en el desarrollo de **FlowStep AI**, detallando la migración de IA, la integración real con Notion, y las optimizaciones de rendimiento del sistema.

---

## 🚀 Sprint 4 — Integración Real de Notion y Migración a Google Gemini

En este sprint se habilitó el funcionamiento en producción real con APIs externas y se resolvieron problemas de consistencia lógica en el backend y control de sesiones.

### 1. Conexión Real con Notion Workspace
* **Bases de Datos Reales:** Se integró la API REST oficial de Notion mediante el token de integración y el ID de página raíz definidos en el entorno local (`.env`).
* **Inicializador de Base de Datos:** Se implementó y ejecutó el script `setup_databases.py` para construir automáticamente las tablas de base de datos en Notion:
  * `FlowStep Tasks` (con propiedades estructuradas de estado, prioridad, esfuerzo, tipo y notas).
  * `FlowStep Agent Log` (para registrar el historial de acciones realizadas por los agentes).
* **Confirmación de Salud:** Se validó la conexión exitosa retornando el estado `notion_connected: true` a través de la ruta `/health`.

### 2. Migración a Google Gemini
* **Proveedor e Infraestructura:** Se migró OpenClaw (`openclaw.json`) para usar el proveedor `google` con la API key de Gemini.
* **Modelo Recomendado:** Se configuró el agente con el modelo `google/gemini-3.1-pro-preview` (y posteriormente `google/gemini-2.5-flash` para optimizar cuotas de rate limit) para realizar el triage de tareas y las propuestas del agente ejecutor de manera real.
* **Modo Real Activo:** Se actualizó `openclaw_client.py` en el backend para desactivar el modo mock automáticamente cuando se detecte la presencia de `GEMINI_API_KEY`.

### 3. Redirección y Control de Sesión Expirada (HTTP 401)
* **Interceptores en Frontend:** Se agregaron validaciones globales en React (`App.jsx` y páginas secundarias) para atrapar respuestas `401 Unauthorized` de la API (indicando que el token de sesión JWT ha expirado).
* **Auto-limpieza y Redirección:** Si el token expira, el frontend limpia instantáneamente el almacenamiento local (`localStorage`) y redirige automáticamente al usuario a la Landing Page para iniciar sesión con un solo clic, previniendo estados inconsistentes en la interfaz.

### 4. Corrección de Mapeo de Rutas (Regex dinámico)
* **Inferencia Inteligente:** Se refactorizó la lógica en `backend/routers/tasks.py` para inferir de manera dinámica y flexible las rutas de archivos de las tareas a partir del enunciado del usuario mediante expresiones regulares (por ejemplo, localizando patrones como `data/prueba.py`), en lugar de forzar por defecto la ruta `src/app.py` en archivos de tipo python.

---

## ⚡ Sprint 5 — Optimización de Latencia y Auto-recuperación (Self-healing)

En este sprint nos enfocamos en erradicar por completo la latencia de red percibida al interactuar con Notion y en añadir mecanismos de tolerancia a fallos en el registro de logs.

### 1. Verificación en Segundo Plano (`BackgroundTasks`)
* **Eliminación de Bloqueos:** Se actualizó el endpoint `POST /tasks/{task_page_id}/verify` en `notion_routes.py` para procesar la actualización del historial de notas en Notion de manera asíncrona mediante `BackgroundTasks` de FastAPI.
* **Reducción del Tiempo de Espera:** Esto reduce el tiempo de respuesta del endpoint de verificación de ~3.5 segundos a **menos de 50 milisegundos**, permitiendo que el validador local de archivos entregue feedback inmediato al usuario sin esperar la latencia de Notion.

### 2. Actualización de Interfaz Instantánea y Optimista (Snappy UI)
* Se rediseñaron los manejadores del tablero Kanban en React (`Kanban.jsx`) para actualizar el estado local de forma proactiva:
  * **Verificación Instantánea:** Al completarse la validación física, el resultado de `verificado: true` se inyecta inmediatamente en la tarjeta, haciendo aparecer el botón de completado (`✅`) en milisegundos.
  * **Transición Optimista:** Al mover tarjetas entre columnas (o marcarlas como completadas), el tablero las reubica instantáneamente en la columna destino. En background se procesa el cambio en Notion y SQLite. Si ocurriera algún fallo de conexión, la interfaz revierte de forma automática la tarjeta a su estado real en el background.
  * **Ejecuciones con IA:** Progresa el estado a *In Progress* al instante en base a la respuesta directa del agente ejecutor.

### 3. Auto-recuperación de Logs del Agente (Self-healing)
* **Tolerancia a Bases de Datos sin Relación:** En bases de datos existentes de Notion donde la propiedad de relación `"Task"` no fue creada inicialmente, la API de Notion retornaba un error `400 Bad Request` ("Task is not a property that exists") al intentar escribir los logs de actividad.
* **Mecanismo de Reintento:** Se añadió un bloque de auto-recuperación en `backend/notion/client.py`: si el registro del log falla por falta de la propiedad `"Task"`, el cliente registra una advertencia, remueve la propiedad `"Task"` de la petición y **reintenta el guardado automáticamente de forma exitosa**, manteniendo la actividad de logs en Notion activa sin interrumpir el flujo.

### 4. Corrección en Creación de Relaciones
* **Setup Robusto:** Se actualizó `setup_databases.py` para pasar el ID de la base de datos de tareas creada a la función de creación de logs de agentes. Esto permite que las nuevas creaciones de base de datos establezcan la relación `"Task"` de manera correcta y nativa en Notion.
