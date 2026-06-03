# FlowStep AI — Backend: correcciones de seguridad y bugs

Este documento resume los arreglos aplicados al backend tras la auditoría de
seguridad/calidad. Cada sección indica el problema, el archivo afectado y el
cambio realizado.

> **Nota de despliegue:** ahora existe una variable `ENVIRONMENT`. En
> `ENVIRONMENT=production` la app **no arranca** si detecta secretos por defecto
> inseguros. En desarrollo solo emite advertencias.

---

## 1. Configuración centralizada (`config.py` — nuevo)

Se creó `backend/config.py` como única fuente de verdad para variables de
entorno. Lee y parsea de forma segura:

- `JWT_SECRET`, `JWT_ALGORITHM`, `SESSION_TIMEOUT_MINUTES`
- `OPENCLAW_GATEWAY_URL`, `OPENCLAW_GATEWAY_TOKEN`
- `MAX_TASKS_PER_SESSION`, `CORS_ORIGINS`, `ALLOW_MOCK_FALLBACK`, `ENVIRONMENT`

Incluye `validate_production_config()`, invocada en el `lifespan` de `main.py`,
que aborta el arranque en producción con secretos inseguros.

## 2. Secretos por defecto eliminados (Crítico)

- **`middleware/jwt_auth.py`**, **`routers/auth.py`**: el `JWT_SECRET` ya no usa
  el literal `"change-me-in-production"` repartido por el código; ambos leen el
  valor desde `config.JWT_SECRET`.
- **`agent/openclaw_client.py`**: se eliminó el token hardcodeado
  `"flowstep-secret-token-123"`; ahora viene de `config.OPENCLAW_GATEWAY_TOKEN`.
- En producción, `validate_production_config()` rechaza estos defaults.

## 3. IDOR en rutas de Notion (Crítico)

`routers/notion_routes.py`:

- `GET /api/v1/notion/tasks`: se eliminó el parámetro `session_id` arbitrario.
  El `session_id` se toma **siempre** del token JWT autenticado.
- `POST /tasks/{id}/execute`, `/complete`, `/review`, `/move`: se añadió el
  helper `_verify_task_ownership()` que carga la tarea desde Notion y verifica
  que su `Session ID` coincide con el del token antes de ejecutar la acción
  (404 si no existe, 403 si pertenece a otra sesión).

## 4. Re-triage transaccional y sincronización SQLite ↔ Notion (Crítico)

`routers/tasks.py` (`POST /session/{id}/tasks`):

- **Antes:** se borraban las tareas de SQLite y se hacía commit *antes* del
  triaje; si el triaje fallaba, se perdían los datos. Además, al re-ejecutar,
  Notion omitía duplicados y SQLite quedaba vacío/parcial (desincronización).
- **Ahora:** primero se ejecuta el triaje (Notion es la fuente de verdad),
  luego se re-lee el tablero completo de la sesión desde Notion y se reconstruye
  SQLite con **delete + insert en una sola transacción** (rollback ante error).
- Se mapea el estado del Kanban de Notion (inglés) al vocabulario local en
  español vía `_NOTION_TO_LOCAL_STATUS`, y se recalcula `completed`.
- El `raw_input` por índice (que se corrompía al omitir duplicados) ya no se usa.

## 5. Mapeo de campos del LLM (Crítico)

`agents/organizer.py`:

- El LLM real devuelve claves en español (`urgencia`, `esfuerzo`, `tipo`,
  `order_index`) mientras el mock usa inglés (`urgency`, `effort`). El Organizer
  ahora acepta **ambas** convenciones, evitando que las prioridades caigan
  siempre a "Media"/"Medio".
- Se eliminaron imports sin usar (`json`, `uuid`).

## 6. Rate limiting conectado (Alto)

- **`middleware/rate_limit.py`**: se añadió `check_session_creation_rate_limit()`
  por IP (10 sesiones / 60s) para frenar el "JWT farming".
- **`routers/auth.py`**: `POST /auth/session` ahora aplica ese límite por IP.
- **`routers/tasks.py`**: `POST /session/{id}/tasks` usa el límite por sesión
  (`check_rate_limit`).

## 7. Gateway configurable y sin mock silencioso en producción (Alto)

`agent/openclaw_client.py`:

- `gateway_url` se lee de `OPENCLAW_GATEWAY_URL` (antes estaba hardcodeado).
- Nuevo helper `_fallback_or_raise()`: en desarrollo cae al mock (con log),
  pero en producción (`ALLOW_MOCK_FALLBACK=false`) lanza error en vez de
  simular silenciosamente que la IA respondió.
- Se corrigió el parseo de JSON envuelto en markdown: `_strip_markdown_fences()`
  reemplaza el frágil `lstrip("```json")/rstrip("```")` que podía corromper JSON.

## 8. Alineación de variables de entorno (Medio)

- **`notion/setup_databases.py`**: el script CLI ahora lee `NOTION_ROOT_PAGE_ID`
  (nombre documentado), con `NOTION_PARENT_PAGE_ID` como fallback legado.
- **`routers/tasks.py`**: el límite de tareas usa `MAX_TASKS_PER_SESSION` en
  lugar de un `20` hardcodeado.
- **`main.py`**: respeta `LOG_LEVEL` y configura `CORS_ORIGINS` desde el entorno.
- **`.env.example`**: documenta `ENVIRONMENT`, `OPENCLAW_GATEWAY_URL`,
  `OPENCLAW_GATEWAY_TOKEN`, `CORS_ORIGINS` y `ALLOW_MOCK_FALLBACK`.

## 9. Fuga de información en errores (Alto/Medio)

- **`middleware/jwt_auth.py`**: el detalle `Invalid token: {exc}` se reemplazó
  por un mensaje genérico (se registra el detalle en logs).
- **`routers/auth.py`**, **`routers/tasks.py`**, **`routers/notion_routes.py`**:
  los `detail=f"...: {exc}"` se reemplazaron por mensajes genéricos, registrando
  la excepción completa con `logger.error`.

## 10. Validación y Pydantic v2 (Medio/Bajo)

- **`routers/tasks.py`**: `TriageRequest` migró `min_items/max_items` →
  `min_length/max_length` (API correcta de Pydantic v2) y añade un validador que
  rechaza tareas vacías. `TaskResponse` usa `ConfigDict(from_attributes=True)`.
- **`notion/schemas.py`**: `CreateTaskRequest` valida con patrones los campos
  `status`, `priority`, `effort`, `type`, `agent`; los modelos migraron a
  `ConfigDict`.

## 11. Dependencias (Medio)

- **`requirements.txt`**: se añadieron cotas superiores de versión a todas las
  dependencias y se fijó `pydantic` explícitamente, para builds reproducibles.

---

## Limitaciones conocidas / fuera de alcance

Estos puntos del informe **no** se abordaron en esta tanda (mayor esfuerzo o
diseño):

- SQLAlchemy síncrono dentro de rutas `async` (bloqueo del event loop).
- `GET /api/v1/notion/agent-log` sigue devolviendo actividad global (el modelo
  de log de Notion no guarda `session_id`).
- `MCPAuditLog` y `verify_file()` siguen sin implementación real (Fase C).
- Sin pruebas automatizadas para el backend.

## Variables de entorno nuevas

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `production` activa validación estricta de secretos |
| `OPENCLAW_GATEWAY_URL` | `http://openclaw:18789` | URL del Gateway OpenClaw |
| `OPENCLAW_GATEWAY_TOKEN` | (vacío) | Token del Gateway (requerido con LLM real) |
| `CORS_ORIGINS` | `http://localhost:3000` | Orígenes permitidos (separados por coma) |
| `ALLOW_MOCK_FALLBACK` | `true` | Permite caer al mock; forzado a `false` en producción |
| `MAX_TASKS_PER_SESSION` | `20` | Máximo de tareas por triaje |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
