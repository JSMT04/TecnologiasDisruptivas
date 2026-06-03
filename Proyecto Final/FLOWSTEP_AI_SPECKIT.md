# FlowStep AI — SPEC KIT v1.0
> **Metodología:** Spec Driven Development (SDD)  
> **Target AI:** Claude Opus 4 (claude-opus-4-5-20251101)  
> **Plataforma:** Desktop únicamente (Windows / macOS / Linux vía Docker)  
> **Estado:** Draft — para revisión del equipo antes de implementación  
> **Equipo:** Juan Diego Camacho · Julian Andres Castaño · Santiago Santamaria Romero · Juan Sebastian Martelo

---

## ÍNDICE

1. [Visión del Producto](#1-visión-del-producto)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Stack Tecnológico](#3-stack-tecnológico)
4. [Requerimientos Funcionales](#4-requerimientos-funcionales)
5. [Requerimientos No Funcionales](#5-requerimientos-no-funcionales)
6. [Modelo de Datos](#6-modelo-de-datos)
7. [Contratos de API Interna](#7-contratos-de-api-interna)
8. [Especificación MCP (OpenClaw)](#8-especificación-mcp-openclaw)
9. [Modelo de Seguridad](#9-modelo-de-seguridad)
10. [Configuración Docker](#10-configuración-docker)
11. [Plantillas de Prompts del Sistema](#11-plantillas-de-prompts-del-sistema)
12. [Criterios de Aceptación](#12-criterios-de-aceptación)
13. [Plan de Implementación por Fases](#13-plan-de-implementación-por-fases)

---

## 1. VISIÓN DEL PRODUCTO

### 1.1 Problema

Las personas pierden tiempo organizando tareas antes de trabajar en ellas. Los asistentes actuales tienen **ceguera de contexto local**: solo saben lo que el usuario les reporta manualmente. Esto genera carga cognitiva, fatiga de decisión y procrastinación.

### 1.2 Solución

**FlowStep AI** es un agente de productividad personal que:
- Recibe pendientes en lenguaje natural.
- Genera un plan diario priorizado con IA.
- **Verifica automáticamente** el progreso real leyendo el sistema de archivos local vía MCP.
- Solo avanza de tarea cuando evidencia concreta lo confirma.

### 1.3 Flujo de Alto Nivel

```
[FASE 1] TRIAGE          →  [FASE 2] ACOMPAÑAMIENTO         →  [FASE 3] CIERRE
Captura pendientes           Guía paso a paso                   Reporte de sesión
Evalúa urgencia/esfuerzo     Verifica entorno local (MCP)        Menú de salida
Genera Hoja de Ruta          Avanza solo con evidencia           Prepara siguiente sesión
Confirmación usuario         Alerta si hay bloqueo
```

---

## 2. ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────┐
│                    DOCKER NETWORK                        │
│                                                          │
│  ┌──────────────┐     HTTP      ┌──────────────────┐    │
│  │   Frontend   │◄────────────►│   Backend API    │    │
│  │  React+Vite  │  :3000→:8000  │   FastAPI        │    │
│  └──────────────┘               └────────┬─────────┘    │
│                                          │               │
│                                   ┌──────▼──────┐        │
│                                   │  OpenClaw   │        │
│                                   │  Agent Core │        │
│                                   └──────┬──────┘        │
│                                          │               │
│                              ┌───────────┼──────────┐   │
│                              ▼           ▼          ▼   │
│                         Claude API   MCP Server  SQLite  │
│                         (Externo)    (Local FS)  (Local) │
│                                          │               │
│                                   [Allow-list]           │
│                                   carpetas permitidas    │
└──────────────────────────────────────────────────────────┘
                              │
                    HOST FILESYSTEM
                    (montado vía volumen Docker,
                     solo directorios en allow-list)
```

### 2.1 Componentes

| Componente | Responsabilidad |
|---|---|
| **Frontend (React)** | UI de sesión: entrada de tareas, Hoja de Ruta, progreso, reporte final |
| **Backend API (FastAPI)** | Orquestación de sesiones, gestión de estado, validación de entradas |
| **OpenClaw Agent** | Core del agente: razonamiento, invocación de herramientas MCP, control de flujo |
| **MCP Filesystem Server** | Acceso controlado al sistema de archivos local con allow-list estricta |
| **SQLite** | Persistencia local: sesiones, tareas, logs de auditoría |
| **Claude API** | LLM subyacente: planificación, triage, resúmenes |

---

## 3. STACK TECNOLÓGICO

> **Criterio de selección:** FreePay (costo $0 en infraestructura), estable, compatible con Docker.

| Capa | Tecnología | Versión mínima | Justificación |
|---|---|---|---|
| Frontend | React + Vite | React 18, Vite 5 | Rápido, sin costo, hot-reload |
| Estilos | TailwindCSS | 3.x | Utility-first, sin diseño custom costoso |
| Backend | FastAPI (Python) | 0.110+ | Async nativo, tipado, OpenAPI auto |
| Agent Core | OpenClaw + MCP SDK | Latest | Requisito innegociable del proyecto |
| LLM | Claude API (Anthropic) | claude-opus-4-5 | Requisito del proyecto |
| MCP Server | @modelcontextprotocol/server-filesystem | Latest | Oficial, mantenido por Anthropic |
| Base de datos | SQLite + SQLAlchemy | SQLAlchemy 2.x | Local, sin servidor, cero costo |
| Contenedores | Docker + Docker Compose | Docker 24+ | Requisito innegociable |
| Autenticación | JWT (PyJWT) | 2.x | Sin servidor externo |
| Logging | Python logging + archivo rotativo | Stdlib | Auditoría MCP |

### 3.1 Variables de Entorno Requeridas

```env
# .env (NO commitear — agregar a .gitignore)
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<string_aleatorio_256bit>
MCP_ALLOW_LIST=/ruta/abs/proyecto1,/ruta/abs/proyecto2
SESSION_TIMEOUT_MINUTES=480
MAX_TASKS_PER_SESSION=20
LOG_LEVEL=INFO
```

---

## 4. REQUERIMIENTOS FUNCIONALES

### RF-01 — Inicio de Sesión de Trabajo
**Como** usuario,  
**quiero** abrir FlowStep AI y registrar mis pendientes del día en lenguaje natural,  
**para** que el sistema los procese sin que yo tenga que estructurarlos.

**Entradas esperadas:**
- Texto libre, mínimo 3 caracteres por tarea, máximo 500 caracteres por tarea.
- Máximo 20 tareas por sesión.
- Opcional: nivel de urgencia manual (Alta / Media / Baja).

**Salidas esperadas:**
- Lista parseada de tareas con ID asignado.
- Confirmación visual de tareas recibidas antes de procesar.

**Reglas:**
- Si el texto contiene múltiples tareas separadas por salto de línea o coma, el sistema las separa automáticamente.
- Entradas vacías o solo espacios son rechazadas con mensaje de error inline.

---

### RF-02 — Análisis de Urgencia y Esfuerzo (Triage IA)
**Como** sistema,  
**quiero** evaluar cada tarea con IA,  
**para** asignar prioridad objetiva basada en urgencia y esfuerzo estimado.

**Entradas esperadas:**
- Lista de tareas del RF-01.
- Contexto de sesión anterior (si existe): tareas incompletas del día anterior.

**Salidas esperadas:**
- Cada tarea etiquetada con:
  - `urgencia`: Alta / Media / Baja
  - `esfuerzo`: Bajo (≤30min) / Medio (30-120min) / Alto (>120min)
  - `dependencias`: lista de IDs de tareas que deben ir antes (puede ser vacía)
  - `tipo`: `archivo` | `código` | `web` | `comunicación` | `otro`
- Tiempo total estimado de la sesión.

**Reglas:**
- El modelo no puede asignar más de 3 tareas como "Alta urgencia + Alto esfuerzo" simultáneamente.
- Si el total estimado supera 8 horas, el sistema advierte y sugiere aplazar tareas de baja urgencia.

---

### RF-03 — Generación y Confirmación de Hoja de Ruta
**Como** usuario,  
**quiero** ver un plan visual del día antes de empezar,  
**para** poder ajustarlo si no refleja mis prioridades reales.

**Entradas esperadas:**
- Output del RF-02.
- Ajustes manuales opcionales del usuario (reordenar, eliminar, editar estimación).

**Salidas esperadas:**
- Hoja de Ruta ordenada: lista de tareas con orden, estimación y tipo.
- Botón de confirmación explícita ("Comenzar con este plan").
- Botón de edición por tarea individual.

**Reglas:**
- El sistema **no inicia** la Fase 2 sin confirmación explícita del usuario.
- Los cambios manuales del usuario en la Hoja de Ruta se guardan en SQLite antes de continuar.

---

### RF-04 — Acompañamiento Paso a Paso
**Como** usuario,  
**quiero** recibir instrucciones claras para cada tarea activa,  
**para** saber exactamente qué hacer sin tener que pensar en la estructura.

**Entradas esperadas:**
- Tarea activa de la Hoja de Ruta.
- Estado actual del entorno (resultado de verificación MCP, si aplica).

**Salidas esperadas:**
- Descripción detallada del paso actual.
- Instrucciones específicas según el `tipo` de tarea:
  - `archivo`: ruta esperada donde debe crearse/modificarse el archivo.
  - `código`: descripción de qué debe existir en el código.
  - `web`: URL o recurso externo a consultar.
  - `comunicación`: borrador o checklist de la comunicación.
  - `otro`: pasos en lenguaje natural.
- Indicador de progreso visual (ej. "Tarea 2 de 7").

**Reglas:**
- Para tareas tipo `archivo` o `código`, el botón "Marcar como completado" está **deshabilitado** hasta que la verificación MCP confirme el estado esperado.
- Para tareas tipo `web`, `comunicación` y `otro`, el usuario puede marcar manualmente como completado.

---

### RF-05 — Verificación Local vía MCP
**Como** sistema,  
**quiero** leer el sistema de archivos local del usuario,  
**para** verificar objetivamente si una tarea fue completada sin pedirle al usuario que reporte.

**Entradas esperadas:**
- Ruta esperada del archivo o directorio (definida en RF-04).
- Tipo de verificación:
  - `existencia`: ¿el archivo/carpeta existe?
  - `no_vacío`: ¿el archivo tiene contenido (>0 bytes)?
  - `modificado_hoy`: ¿fue modificado en la sesión actual?
  - `sintaxis_json` / `sintaxis_html` / `sintaxis_python`: ¿es parseable?

**Salidas esperadas:**
- `{ "verificado": true/false, "detalle": "string explicativo", "timestamp": "ISO8601" }`
- Si `verificado: false`: mensaje de bloqueo con sugerencia de acción.
- Si `verificado: true`: desbloqueo del botón de avance.

**Reglas:**
- El MCP server **solo puede leer** rutas que estén dentro del `MCP_ALLOW_LIST`.
- Las rutas fuera del allow-list generan error `403 PATH_NOT_ALLOWED` y se registran en el log de auditoría.
- El agente **nunca escribe** en el sistema de archivos durante la verificación (solo lectura).
- La verificación ocurre solo cuando el usuario presiona "Verificar ahora" o cuando pasa un intervalo configurable (default: nunca automático).

---

### RF-06 — Gestión de Bloqueos
**Como** usuario,  
**quiero** reportar que estoy bloqueado en una tarea,  
**para** que el sistema me ayude a desbloquearme o reorganice el plan.

**Entradas esperadas:**
- Botón "Estoy bloqueado" en la tarea activa.
- Descripción opcional del bloqueo en texto libre.

**Salidas esperadas:**
- Sugerencias de desbloqueo contextuales (IA).
- Opción de posponer la tarea al final de la lista.
- Opción de marcarla como "Requiere ayuda externa" (no cuenta como completada).

**Reglas:**
- Una tarea pospuesta puede reactivarse en cualquier momento.
- El sistema registra el bloqueo con timestamp en SQLite.

---

### RF-07 — Reporte de Cierre de Sesión
**Como** usuario,  
**quiero** ver un resumen de lo que hice al finalizar,  
**para** tener trazabilidad real de mi productividad.

**Entradas esperadas:**
- Todas las tareas de la sesión con su estado final.
- Log de verificaciones MCP realizadas.

**Salidas esperadas:**
- Reporte con:
  - Total tareas completadas / pospuestas / bloqueadas.
  - Archivos/carpetas creados o modificados durante la sesión (detectados por MCP).
  - Tiempo total de sesión.
  - Puntuación de productividad simple (completadas / total × 100).
- Exportación del reporte como `.txt` o `.md` en ruta configurable.

**Reglas:**
- El reporte es generado por IA con lenguaje conciso (máx. 300 palabras).
- La exportación usa el MCP server para escribir el archivo en una carpeta previamente incluida en el allow-list.

---

### RF-08 — Menú de Salida
**Como** usuario,  
**quiero** elegir qué hacer al terminar la sesión,  
**para** no tener que pensar en el cierre del entorno de trabajo.

**Opciones disponibles:**
1. **Cerrar FlowStep AI** — Cierra la aplicación limpiamente.
2. **Iniciar descanso** — Muestra un temporizador Pomodoro configurable (5-60 min).
3. **Preparar nuevo proyecto** — El sistema, vía MCP, crea estructura de carpetas base en una ruta del allow-list.

**Entradas para opción 3:**
- Nombre del proyecto.
- Plantilla de estructura: `web` | `data` | `genérico`.
- Ruta destino (debe estar en allow-list).

**Salidas esperadas para opción 3:**
- Carpetas y archivos base creados.
- Confirmación con árbol de directorios resultante.

---

### RF-09 — Historial de Sesiones
**Como** usuario,  
**quiero** ver mis sesiones anteriores,  
**para** continuar tareas pendientes o revisar mi historial de productividad.

**Entradas esperadas:**
- Filtro por fecha (rango).

**Salidas esperadas:**
- Lista de sesiones con fecha, tareas totales, completadas.
- Detalle expandible por sesión.
- Opción "Continuar tareas pendientes" que pre-carga las tareas pospuestas en nueva sesión.

**Reglas:**
- Máximo 90 días de historial almacenado localmente.
- El historial no se sincroniza a ningún servidor externo.

---

### RF-10 — Configuración del Sistema
**Como** usuario,  
**quiero** configurar los parámetros del sistema,  
**para** adaptarlo a mi flujo de trabajo.

**Parámetros configurables:**

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `mcp_allow_list` | lista de rutas | `[]` | Carpetas accesibles por MCP |
| `session_timeout` | entero (min) | 480 | Tiempo máximo de sesión activa |
| `verificacion_auto` | booleano | `false` | Si MCP verifica sin acción del usuario |
| `exportar_reporte_ruta` | ruta | `~/flowstep/reportes` | Destino de reportes de cierre |
| `plantilla_proyecto_default` | enum | `genérico` | Plantilla para RF-08 opción 3 |
| `tema_ui` | enum | `oscuro` | `oscuro` / `claro` |

**Reglas:**
- Los cambios en `mcp_allow_list` requieren reinicio del MCP server.
- Las rutas del allow-list se validan: deben existir en el host antes de ser aceptadas.
- La configuración se almacena en `config.json` local, nunca en la base de datos.

---

## 5. REQUERIMIENTOS NO FUNCIONALES

### RNF-01 — Docker (OBLIGATORIO)
- Todo el sistema debe ejecutarse dentro de contenedores Docker.
- Se usa `docker-compose.yml` como único punto de arranque.
- Comandos de arranque: `docker compose up` (primera vez) / `docker compose start` (sesiones siguientes).
- Los contenedores **no corren como root**. Se define usuario no privilegiado en cada `Dockerfile`.
- El socket de Docker no se expone al contenedor de la aplicación.

### RNF-02 — OpenClaw (OBLIGATORIO)
- El agente core usa OpenClaw como framework de orquestación.
- OpenClaw invoca herramientas MCP para todas las interacciones con el sistema de archivos.
- Las llamadas al LLM (Claude API) pasan siempre a través de OpenClaw, nunca directamente desde el frontend.
- El agente mantiene el estado de la sesión en memoria durante la ejecución y lo persiste en SQLite al finalizar cada tarea.

### RNF-03 — Seguridad de Acceso a Archivos
- El MCP server opera con una allow-list estricta cargada desde `.env`.
- **Ninguna ruta fuera del allow-list puede ser leída ni escrita.**
- El servidor MCP no tiene acceso a rutas del sistema operativo (`/etc`, `/sys`, `C:\Windows`, etc.).
- Las operaciones de escritura (solo RF-07 y RF-08 opción 3) requieren que la ruta esté explícitamente en allow-list Y que la operación sea validada por el agente antes de ejecutarse.

### RNF-04 — Rendimiento
- Tiempo de respuesta del triage (RF-02): ≤ 10 segundos para hasta 20 tareas.
- Tiempo de verificación MCP (RF-05): ≤ 2 segundos para verificación de existencia/tamaño.
- Carga inicial de la UI: ≤ 3 segundos en localhost.
- El backend soporta una sola sesión activa simultánea por instancia (uso personal).

### RNF-05 — Privacidad y Datos Locales
- **Ningún dato de tareas, rutas ni archivos del usuario se envía a servidores externos**, excepto los prompts necesarios para la inferencia en Claude API.
- Los prompts enviados a Claude API **no incluyen contenido de archivos**, solo metadatos (nombre, extensión, tamaño, fecha de modificación).
- El historial de sesiones se almacena únicamente en SQLite local.
- No hay telemetría, analytics ni tracking de ningún tipo.

### RNF-06 — Auditabilidad
- Toda operación del MCP server (lectura o escritura) genera una entrada en `audit.log`:
  ```
  [ISO8601] [OPERACIÓN] [RUTA] [RESULTADO] [SESIÓN_ID]
  ```
- El log es de solo-append (no borrable desde la UI).
- Los logs se rotan diariamente, máximo 30 días de retención.

### RNF-07 — Resiliencia
- Si Claude API falla, el sistema muestra error con opción de reintentar (máx. 3 intentos con backoff exponencial).
- Si el MCP server no puede leer un archivo (permisos del OS), informa al usuario y desbloquea el avance manual.
- Si el backend se cae, el frontend muestra estado de "reconectando" sin perder el estado de la sesión (cargado desde SQLite al reconectar).

### RNF-08 — Seguridad de la API Interna
- Todos los endpoints del backend requieren JWT válido.
- El JWT se genera en el arranque de sesión y expira según `SESSION_TIMEOUT_MINUTES`.
- No hay endpoints públicos sin autenticación, excepto `GET /health`.
- Las entradas de usuario se sanean (strip HTML, validación de longitud) antes de ser procesadas.
- Rate limiting: máximo 60 requests/minuto por sesión activa.

---

## 6. MODELO DE DATOS

### 6.1 Entidad: `Session`
```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,   -- UUID v4
    created_at  TEXT NOT NULL,      -- ISO8601
    ended_at    TEXT,               -- NULL si activa
    status      TEXT NOT NULL,      -- 'active' | 'completed' | 'abandoned'
    total_tasks INTEGER DEFAULT 0,
    completed   INTEGER DEFAULT 0,
    report_path TEXT                -- ruta al .md exportado
);
```

### 6.2 Entidad: `Task`
```sql
CREATE TABLE tasks (
    id            TEXT PRIMARY KEY,  -- UUID v4
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    raw_input     TEXT NOT NULL,     -- texto original del usuario
    title         TEXT NOT NULL,     -- versión procesada
    urgency       TEXT NOT NULL,     -- 'alta' | 'media' | 'baja'
    effort        TEXT NOT NULL,     -- 'bajo' | 'medio' | 'alto'
    type          TEXT NOT NULL,     -- 'archivo' | 'código' | 'web' | 'comunicación' | 'otro'
    order_index   INTEGER NOT NULL,
    status        TEXT NOT NULL,     -- 'pendiente' | 'activa' | 'completada' | 'pospuesta' | 'bloqueada'
    expected_path TEXT,              -- para tareas tipo archivo/código
    started_at    TEXT,
    completed_at  TEXT,
    notes         TEXT               -- notas del usuario o del agente
);
```

### 6.3 Entidad: `MCPAuditLog`
```sql
CREATE TABLE mcp_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    task_id     TEXT,
    timestamp   TEXT NOT NULL,  -- ISO8601
    operation   TEXT NOT NULL,  -- 'READ' | 'WRITE' | 'LIST' | 'DENIED'
    path        TEXT NOT NULL,
    result      TEXT NOT NULL,  -- 'OK' | 'NOT_FOUND' | 'DENIED' | 'ERROR'
    detail      TEXT
);
```

### 6.4 Entidad: `Config`
```
config.json  (archivo, no en DB)
{
  "mcp_allow_list": [],
  "session_timeout": 480,
  "verificacion_auto": false,
  "exportar_reporte_ruta": "",
  "plantilla_proyecto_default": "genérico",
  "tema_ui": "oscuro"
}
```

---

## 7. CONTRATOS DE API INTERNA

> Base URL: `http://localhost:8000/api/v1`  
> Autenticación: `Authorization: Bearer <JWT>` en todos los endpoints excepto `/auth/session` y `/health`

### 7.1 Auth

```
POST /auth/session
Body: {} (vacío, genera nueva sesión)
Response 200: { "token": "JWT", "session_id": "UUID", "expires_at": "ISO8601" }
```

### 7.2 Sesión

```
GET  /session/{session_id}
Response 200: { session object completo con lista de tasks }

POST /session/{session_id}/end
Body: {}
Response 200: { "report": "markdown string", "stats": { completadas, pospuestas, bloqueadas, duracion_min } }
```

### 7.3 Tareas

```
POST /session/{session_id}/tasks
Body: { "raw_tasks": ["tarea 1", "tarea 2", ...] }
Response 200: { "tasks": [ task objects con triage aplicado ] }

PUT /task/{task_id}/status
Body: { "status": "completada" | "pospuesta" | "bloqueada", "notes": "string opcional" }
Response 200: { task object actualizado }

PUT /task/{task_id}/reorder
Body: { "new_index": integer }
Response 200: { "tasks": [ lista reordenada ] }
```

### 7.4 MCP / Verificación

```
POST /mcp/verify
Body: {
  "task_id": "UUID",
  "path": "/ruta/absoluta/archivo.ext",
  "check_type": "existencia" | "no_vacío" | "modificado_hoy" | "sintaxis_json" | "sintaxis_html" | "sintaxis_python"
}
Response 200: { "verificado": bool, "detalle": "string", "timestamp": "ISO8601" }
Response 403: { "error": "PATH_NOT_ALLOWED", "path": "..." }

POST /mcp/create_structure
Body: {
  "project_name": "string",
  "template": "web" | "data" | "genérico",
  "base_path": "/ruta/en/allow-list"
}
Response 200: { "created_paths": ["..."], "tree": "string visual" }
Response 403: { "error": "PATH_NOT_ALLOWED" }
```

### 7.5 Configuración

```
GET  /config
Response 200: { config object }

PUT  /config
Body: { campos a actualizar }
Response 200: { config actualizada }
Response 400: { "error": "INVALID_PATH", "path": "..." }  si ruta no existe en host
```

### 7.6 Historial

```
GET /history?from=YYYY-MM-DD&to=YYYY-MM-DD
Response 200: { "sessions": [ session summaries ] }

POST /history/load-pending
Body: { "session_id": "UUID de sesión anterior" }
Response 200: { "tasks": [ tareas pospuestas/bloqueadas ] }
```

---

## 8. ESPECIFICACIÓN MCP (OpenClaw)

### 8.1 Herramientas MCP Habilitadas

El MCP server expone **únicamente** estas herramientas, con las rutas restringidas al allow-list:

| Herramienta MCP | Operación | Permisos |
|---|---|---|
| `read_file` | Leer contenido de archivo | Solo lectura, solo allow-list |
| `list_directory` | Listar archivos de carpeta | Solo lectura, solo allow-list |
| `get_file_info` | Metadata: tamaño, fecha modificación | Solo lectura, solo allow-list |
| `write_file` | Crear/sobreescribir archivo | Solo escritura, solo allow-list, requiere validación agente |
| `create_directory` | Crear carpeta | Solo escritura, solo allow-list, requiere validación agente |

**NO se habilitan:**
- `move_file`, `delete_file`, `execute_command`, `search_files` (recursivo en raíz)

### 8.2 Configuración del MCP Server

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "<ruta_1_del_allow_list>",
        "<ruta_2_del_allow_list>"
      ]
    }
  }
}
```

> Las rutas se inyectan dinámicamente desde `MCP_ALLOW_LIST` en el arranque del backend.  
> Si `MCP_ALLOW_LIST` está vacío, el MCP server **no arranca** y las verificaciones de archivo quedan deshabilitadas.

### 8.3 Flujo de Verificación del Agente

```
Usuario presiona "Verificar ahora"
        │
        ▼
Backend valida que path ∈ allow-list
        │ NO → 403 PATH_NOT_ALLOWED → log auditoría
        │ SÍ ↓
OpenClaw llama herramienta MCP correspondiente
        │
        ▼
MCP server ejecuta operación en filesystem
        │
        ▼
Resultado → Backend → log auditoría → respuesta al Frontend
        │
        ▼
Si verificado=true → Frontend desbloquea "Avanzar"
Si verificado=false → Frontend muestra mensaje de bloqueo
```

---

## 9. MODELO DE SEGURIDAD

### 9.1 Capas de Seguridad

```
CAPA 1 — CONTENEDOR
├── Usuario no-root en Docker
├── No privilegios de admin del host
├── Solo puertos 3000 y 8000 expuestos (localhost únicamente)
└── Sin acceso al socket Docker desde contenedores de app

CAPA 2 — API BACKEND
├── JWT con expiración
├── Rate limiting (60 req/min)
├── Sanitización de inputs (longitud, strip HTML)
└── CORS configurado solo para localhost:3000

CAPA 3 — MCP / FILESYSTEM
├── Allow-list de rutas validada al arranque
├── Sin herramientas destructivas habilitadas
├── Escritura solo en operaciones explícitas (reporte y estructura de proyecto)
└── Toda operación auditada en audit.log

CAPA 4 — LLM / CLAUDE API
├── Prompts NO incluyen contenido de archivos del usuario
├── API key almacenada solo en .env (nunca en código ni en DB)
├── .env en .gitignore obligatoriamente
└── Comunicación solo vía HTTPS
```

### 9.2 Reglas Críticas de Seguridad

1. **La API key de Anthropic NUNCA se expone al frontend.**
2. **El MCP server nunca procesa rutas construidas con input directo del usuario** — las rutas esperadas son definidas por el agente a partir del contexto de la tarea, no por texto libre del usuario.
3. **Las operaciones de escritura requieren doble validación**: validación de allow-list en backend + validación semántica del agente ("¿tiene sentido escribir aquí para esta tarea?").
4. **El servidor no acepta rutas con traversal** (`../`, `..\\`, rutas absolutas fuera de allow-list).
5. **Los logs de auditoría son inmutables desde la UI** — solo accesibles por el sistema operativo del host.
6. **En producción (uso real), los puertos deben estar restringidos a 127.0.0.1** — nunca expuestos a la red local.

### 9.3 `.gitignore` Obligatorio

```gitignore
.env
*.env.local
*.db
audit.log
logs/
node_modules/
__pycache__/
.venv/
```

---

## 10. CONFIGURACIÓN DOCKER

### 10.1 Estructura de Directorios del Proyecto

```
flowstep-ai/
├── docker-compose.yml
├── .env.example           ← plantilla sin valores reales
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py            ← FastAPI entrypoint
│   ├── agent/             ← OpenClaw core
│   ├── mcp/               ← MCP client wrapper
│   ├── models/            ← SQLAlchemy models
│   ├── routers/           ← FastAPI routers
│   └── config.json        ← generado en primer arranque
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── pages/
│       │   ├── Triage.jsx
│       │   ├── RoadMap.jsx
│       │   ├── ActiveTask.jsx
│       │   ├── Report.jsx
│       │   └── History.jsx
│       └── components/
└── data/                  ← montado como volumen, gitignored
    ├── flowstep.db
    └── audit.log
```

### 10.2 `docker-compose.yml`

```yaml
version: "3.9"

services:
  backend:
    build: ./backend
    container_name: flowstep-backend
    user: "1000:1000"                      # usuario no-root
    ports:
      - "127.0.0.1:8000:8000"              # solo localhost
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - MCP_ALLOW_LIST=${MCP_ALLOW_LIST}
      - SESSION_TIMEOUT_MINUTES=${SESSION_TIMEOUT_MINUTES:-480}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./data:/app/data
      - ${MCP_ALLOW_LIST_VOLUME}:/workspace:ro  # montaje read-only por defecto
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  frontend:
    build: ./frontend
    container_name: flowstep-frontend
    user: "1000:1000"
    ports:
      - "127.0.0.1:3000:3000"              # solo localhost
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

> **Nota sobre volúmenes y allow-list:** Los paths del `MCP_ALLOW_LIST` deben montarse explícitamente en el `docker-compose.yml`. El README debe documentar cómo editar el compose para agregar nuevas rutas permitidas. Esto es una decisión deliberada de seguridad: los paths no se auto-descubren.

### 10.3 `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalar Node.js para el MCP server
RUN apt-get update && apt-get install -y nodejs npm curl && rm -rf /var/lib/apt/lists/*

# Instalar MCP filesystem server globalmente
RUN npm install -g @modelcontextprotocol/server-filesystem

# Usuario no-root
RUN useradd -m -u 1000 appuser
USER appuser

COPY --chown=appuser requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=appuser . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.4 `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine

WORKDIR /app

RUN addgroup -g 1000 appgroup && adduser -u 1000 -G appgroup -s /bin/sh -D appuser
USER appuser

COPY --chown=appuser package*.json ./
RUN npm ci --only=production

COPY --chown=appuser . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
```

---

## 11. PLANTILLAS DE PROMPTS DEL SISTEMA

> **Principio de optimización:** Los prompts son los más cortos posibles que producen output estructurado correcto. Se usa XML para delimitar secciones. El contenido de archivos nunca se incluye.

### 11.1 Prompt de Sistema — Agente Principal

```xml
<system>
Eres FlowStep AI, un agente de productividad personal. Tu rol es:
1. Analizar tareas del usuario y crear un plan diario priorizado.
2. Guiar al usuario paso a paso, tarea por tarea.
3. Usar herramientas MCP para verificar progreso real en el filesystem.
4. Generar reportes concisos al finalizar.

Reglas estrictas:
- Responde SIEMPRE en español.
- Nunca inventes paths o nombres de archivos que no hayas verificado.
- Para verificar archivos, usa SOLO las herramientas MCP disponibles.
- Los prompts de verificación incluyen solo metadata (nombre, extensión, tamaño, fecha), nunca contenido de archivos.
- Si no puedes completar una acción con las herramientas disponibles, di exactamente qué falta.
- Sé conciso. Máximo 150 palabras por respuesta al usuario.
</system>
```

### 11.2 Prompt de Triage

```xml
<task>Analiza estas tareas y devuelve JSON válido únicamente, sin texto extra.</task>
<input>
Tareas: {raw_tasks_json}
Contexto previo: {pending_from_yesterday}
</input>
<output_schema>
{
  "tasks": [
    {
      "id": "UUID",
      "title": "string (máx 80 chars)",
      "urgencia": "alta|media|baja",
      "esfuerzo": "bajo|medio|alto",
      "tipo": "archivo|código|web|comunicación|otro",
      "dependencias": ["UUID"],
      "order_index": integer,
      "expected_path": "string|null",
      "instrucciones": "string (máx 200 chars)"
    }
  ],
  "tiempo_total_estimado_min": integer,
  "advertencia": "string|null"
}
</output_schema>
```

### 11.3 Prompt de Verificación de Tarea

```xml
<task>Determina si la tarea fue completada basándote en la metadata del archivo.</task>
<tarea_activa>{task_title} - tipo: {task_type}</tarea_activa>
<mcp_resultado>
path: {path}
existe: {bool}
tamaño_bytes: {int}
ultima_modificacion: {ISO8601}
verificacion_tipo: {check_type}
resultado_sintaxis: {bool|null}
</mcp_resultado>
<output_schema>
{
  "verificado": bool,
  "confianza": "alta|media|baja",
  "detalle": "string (máx 100 chars)",
  "accion_sugerida": "string|null"
}
</output_schema>
```

### 11.4 Prompt de Reporte de Cierre

```xml
<task>Genera reporte de sesión en Markdown. Máximo 300 palabras. Sin secciones adicionales.</task>
<sesion>
Duración: {duracion_min} minutos
Completadas: {completadas}/{total}
Pospuestas: {pospuestas}
Bloqueadas: {bloqueadas}
Archivos detectados por MCP: {archivos_modificados_json}
</sesion>
<formato>
# Reporte FlowStep AI — {fecha}
## Resumen
[párrafo]
## Logros
[lista]
## Pendiente para mañana
[lista o "Ninguno"]
## Nota del agente
[observación breve]
</formato>
```

---

## 12. CRITERIOS DE ACEPTACIÓN

### 12.1 Fase 1 — Triage

| ID | Criterio | Método de verificación |
|---|---|---|
| CA-01 | El sistema parsea correctamente hasta 20 tareas en una entrada con saltos de línea | Test unitario con input de 20 líneas |
| CA-02 | El triage produce JSON válido con todos los campos requeridos | Validación de esquema con Pydantic |
| CA-03 | El triage no inicia sin confirmación del usuario | Test E2E: verificar que POST /session/{id}/tasks no activa la Fase 2 |
| CA-04 | Entradas vacías son rechazadas con error inline (no excepción 500) | Test unitario de validación |
| CA-05 | El tiempo de triage para 20 tareas es ≤ 10 segundos | Test de performance con mock de Claude API |

### 12.2 Fase 2 — Verificación MCP

| ID | Criterio | Método de verificación |
|---|---|---|
| CA-06 | Una ruta fuera del allow-list retorna 403 y registra en audit.log | Test de integración con path inválido |
| CA-07 | La verificación de existencia detecta correctamente archivo presente/ausente | Test con archivo real en directorio de test |
| CA-08 | El botón "Avanzar" permanece deshabilitado hasta `verificado: true` | Test E2E de UI |
| CA-09 | El MCP server no ejecuta operaciones de escritura durante verificación | Inspección de herramientas habilitadas + test de integración |
| CA-10 | La verificación de sintaxis JSON detecta JSON inválido correctamente | Test unitario con archivo JSON malformado |

### 12.3 Fase 3 — Cierre

| ID | Criterio | Método de verificación |
|---|---|---|
| CA-11 | El reporte incluye archivos modificados detectados por MCP en la sesión | Test con sesión que modifica archivos reales |
| CA-12 | La exportación del reporte crea el archivo `.md` en la ruta configurada | Verificación de existencia del archivo post-sesión |
| CA-13 | La opción "Preparar nuevo proyecto" crea la estructura correcta según plantilla | Test con plantilla `web` y verificación de árbol |

### 12.4 Seguridad

| ID | Criterio | Método de verificación |
|---|---|---|
| CA-14 | La API key de Anthropic no aparece en ninguna respuesta del backend | Inspección de logs y responses |
| CA-15 | Los contenedores no corren como root | `docker inspect` — verificar usuario |
| CA-16 | Los puertos solo están expuestos en 127.0.0.1 | `docker ps` — verificar binding |
| CA-17 | El JWT expira según `SESSION_TIMEOUT_MINUTES` | Test de integración con token expirado |
| CA-18 | Path traversal (`../`) es rechazado por el backend | Test de seguridad con input malicioso |

---

## 13. PLAN DE IMPLEMENTACIÓN POR FASES

> **Prioridad:** Funcional > Completo. Cada fase debe pasar sus criterios de aceptación antes de avanzar.

### Fase A — Infraestructura Base (Sprint 1)

**Objetivo:** Docker funcionando, backend levantado, frontend conectado.

1. Crear estructura de directorios del proyecto.
2. Implementar `docker-compose.yml` + Dockerfiles.
3. Implementar `GET /health` y `POST /auth/session`.
4. Crear modelos SQLAlchemy y migración inicial.
5. Configurar CORS, JWT y rate limiting en FastAPI.
6. Crear página de inicio en React (solo UI, sin lógica).

**Definición de done:** `docker compose up` levanta ambos servicios; frontend carga en `localhost:3000`; backend responde en `/health`.

---

### Fase B — Triage y Hoja de Ruta (Sprint 2)

**Objetivo:** El usuario puede ingresar tareas y recibir un plan priorizado.

1. Integrar Claude API en el backend (via OpenClaw).
2. Implementar `POST /session/{id}/tasks` con el prompt de triage.
3. Implementar Pydantic validation del output del LLM.
4. Construir UI de Triage (input de tareas) y UI de Hoja de Ruta (visualización + edición + confirmación).
5. Implementar `PUT /task/{id}/reorder`.

**Definición de done:** CA-01 a CA-05 pasan.

---

### Fase C — Verificación MCP (Sprint 3)

**Objetivo:** El agente verifica el filesystem real y controla el avance.

1. Configurar MCP server con allow-list.
2. Implementar cliente MCP en el backend (wrapper sobre OpenClaw).
3. Implementar `POST /mcp/verify` con todos los tipos de verificación.
4. Conectar UI de tarea activa con el endpoint de verificación.
5. Implementar lógica de bloqueo/desbloqueo del botón "Avanzar".
6. Implementar audit.log.

**Definición de done:** CA-06 a CA-10 pasan.

---

### Fase D — Cierre y Configuración (Sprint 4)

**Objetivo:** El flujo completo funciona end-to-end.

1. Implementar `POST /session/{id}/end` con generación de reporte vía LLM.
2. Implementar exportación de reporte vía MCP.
3. Implementar `POST /mcp/create_structure`.
4. Construir UI de Reporte final y Menú de salida.
5. Implementar pantalla de Configuración.
6. Implementar pantalla de Historial.

**Definición de done:** CA-11 a CA-13 pasan; flujo completo E2E funciona sin errores.

---

### Fase E — Seguridad y Hardening (Sprint 5)

**Objetivo:** El sistema es seguro para uso real.

1. Auditar todos los endpoints con OWASP Top 10 checklist.
2. Implementar sanitización de inputs y protección contra path traversal.
3. Verificar que todos los contenedores corren como non-root.
4. Verificar binding de puertos a 127.0.0.1.
5. Revisar que `.env` y `data/` están en `.gitignore`.
6. Ejecutar todos los criterios de aceptación de seguridad (CA-14 a CA-18).
7. Documentar `README.md` con instrucciones de configuración del allow-list.

**Definición de done:** CA-14 a CA-18 pasan; README permite a alguien externo levantar el proyecto.

---

## APÉNDICE — Estructura de Plantillas de Proyecto (RF-08 opción 3)

### Plantilla `web`
```
{project_name}/
├── index.html
├── styles/
│   └── main.css
├── scripts/
│   └── main.js
├── assets/
└── README.md
```

### Plantilla `data`
```
{project_name}/
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
├── src/
│   └── main.py
├── requirements.txt
└── README.md
```

### Plantilla `genérico`
```
{project_name}/
├── docs/
├── src/
├── tests/
└── README.md
```

---

*FlowStep AI SPEC KIT v1.0 — Generado para el equipo de desarrollo. Última actualización: 2025.*
