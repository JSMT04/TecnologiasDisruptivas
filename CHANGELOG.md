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

### 5. Soporte para Auditoría de Archivos en el Escritorio (D:)
* **Montaje del Volumen:** Se agregó un nuevo mapeo de volumen en `docker-compose.yml` (`${HOST_DESKTOP_PATH:-D:/Desktop}:/app/desktop`) para enlazar el escritorio físico del host (en el disco `D:`) al contenedor de backend en la ruta `/app/desktop`.
* **Políticas de Acceso (Sandbox):** Se configuraron y expusieron las variables `HOST_DESKTOP_PATH=D:\Desktop` y `MCP_ALLOW_LIST=/app,/app/desktop` en el archivo `.env` para otorgar los permisos de lectura, verificación y análisis sintáctico a cualquier archivo ubicado en el Escritorio, de forma totalmente transparente e inmune a restricciones de sandboxing.

---

## 🤖 Sprint 6 — Agente Auto-Verificador en Segundo Plano y Auto-Completado de Tareas

En este sprint se introdujo automatización activa continua para auditar el sistema de archivos del usuario sin necesidad de intervención manual o clics en la interfaz.

### 1. Loop de Auto-Verificación en Segundo Plano (Background Agent)
* **Monitoreo Asíncrono:** Se diseñó e implementó un servicio en segundo plano ([auto_verifier.py](file:///c:/Users/Usuario/FlowStep%20AI/flowstep-ai/backend/agents/auto_verifier.py)) que corre indefinidamente como una tarea `asyncio` cada 5 segundos a nivel de la aplicación FastAPI.
* **Escaneo de Tareas en Progreso:** El agente consulta la base de datos local (SQLite) buscando tareas que tengan especificada una ruta esperada (`expected_path`) pero que no hayan sido verificadas con éxito en el log de auditoría.
* **Auditoría Silenciosa:** De manera autónoma, el agente audita la existencia, tamaño y sintaxis del archivo objetivo local (incluyendo soporte para el Escritorio de Windows montado en `/app/desktop`).

### 2. Auto-Completado Automático (Auto-Move to Done)
* **Sincronización Inteligente:** Al momento en que el agente auto-verificador detecta que el archivo local existe y es válido, escribe de forma asíncrona la auditoría `OK`, añade una nota en la tarea de Notion informando la verificación exitosa, y **mueve automáticamente el estado de la tarea a "Done"** en Notion.

### 3. Ajuste de Sincronización del Frontend (Snappy Sync)
* **Intervalo de Refresco Reducido:** Se ajustó el temporizador del tablero Kanban en React (`Kanban.jsx`) de 15 segundos a **5 segundos** para que los movimientos automatizados realizados por el agente auto-verificador en Notion se sincronicen casi de inmediato en la pantalla del usuario.

### 4. Soporte para el Escritorio Real de Windows
* **Corrección de Ruta de Montaje:** Se actualizó la variable de entorno `HOST_DESKTOP_PATH` en el `.env` para apuntar a la ubicación real del escritorio de usuario en Windows (`D:\Usuarios\Juan Martelo\Desktop`), permitiendo que el volumen de Docker monte directamente la carpeta activa de trabajo del usuario en lugar de un directorio fantasma.
