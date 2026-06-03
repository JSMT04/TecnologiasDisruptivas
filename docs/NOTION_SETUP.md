# 🔧 Guía de Configuración de Notion para FlowStep AI

Esta guía te lleva paso a paso para conectar FlowStep AI con tu workspace de Notion.

---

## Paso 1: Crear una cuenta de Notion (si no tienes una)

1. Ve a [notion.so](https://www.notion.so/) y crea una cuenta gratuita.
2. Crea un nuevo workspace o usa uno existente.

---

## Paso 2: Crear una Integration (API Token)

1. Ve a [notion.so/profile/integrations](https://www.notion.so/profile/integrations)
2. Haz clic en **"+ New integration"** (o "Crear nueva integración")
3. Configura la integración:
   - **Nombre:** `FlowStep AI`
   - **Logo:** (opcional)
   - **Workspace asociado:** Selecciona tu workspace
   - **Capabilities (Permisos):**
     - ✅ Read content
     - ✅ Insert content
     - ✅ Update content
     - ❌ Delete content (no necesario)
   - **Content Capabilities:**
     - ✅ Read comments (opcional)
     - ✅ Insert comments (opcional)
4. Haz clic en **"Save"**
5. **Copia el "Internal Integration Secret"** — empieza con `secret_...`

> ⚠️ **IMPORTANTE:** Guarda este token de forma segura. No lo compartas ni lo subas a Git.

---

## Paso 3: Crear la página raíz en Notion

1. En tu workspace de Notion, crea una nueva **página** llamada `FlowStep AI`
2. Esta página será el contenedor de las bases de datos del Kanban y el log de agentes.

---

## Paso 4: Compartir la página con la Integration

1. Abre la página `FlowStep AI` que acabas de crear
2. Haz clic en el menú **`...`** (tres puntos) en la esquina superior derecha
3. Selecciona **"Connections"** o **"Conectar con"**
4. Busca tu integración `FlowStep AI` y selecciónala
5. Confirma el acceso

> 📝 **NOTA:** Sin este paso, la API no podrá acceder a la página ni crear bases de datos dentro de ella.

---

## Paso 5: Obtener el Page ID de la página raíz

1. Abre la página `FlowStep AI` en tu navegador
2. La URL tendrá este formato:
   ```
   https://www.notion.so/FlowStep-AI-abc123def456...
   ```
3. El **Page ID** son los últimos 32 caracteres de la URL (sin guiones):
   ```
   abc123def456789012345678901234ab
   ```
4. Formátalo con guiones así (formato UUID):
   ```
   abc123de-f456-7890-1234-5678901234ab
   ```

> 💡 **TIP:** También puedes hacer clic derecho en la página → "Copy link" y extraer el ID de ahí.

---

## Paso 6: Configurar las variables de entorno

Abre el archivo `.env` en la raíz del proyecto (`flowstep-ai/.env`) y agrega:

```env
# Notion Integration
NOTION_API_TOKEN=secret_tu_token_aqui
NOTION_ROOT_PAGE_ID=tu-page-id-aqui-en-formato-uuid

# Estos se llenan automáticamente después del setup:
NOTION_TASKS_DB_ID=
NOTION_LOG_DB_ID=
```

---

## Paso 7: Ejecutar el setup de bases de datos

Una vez configuradas las variables de entorno, ejecuta el script de setup:

### Opción A: Dentro de Docker (recomendado)
```bash
docker compose exec backend python -m notion.setup_databases
```

### Opción B: Localmente (si tienes Python 3.12+ instalado)
```bash
cd backend
pip install httpx python-dotenv
python -m notion.setup_databases
```

El script creará automáticamente:
- 📋 **FlowStep Tasks** — Base de datos Kanban con todas las propiedades
- 📊 **Agent Activity Log** — Registro de actividad de agentes

Los IDs de las bases de datos se mostrarán en la consola. Cópialos al `.env`:

```env
NOTION_TASKS_DB_ID=id-de-la-base-de-tareas
NOTION_LOG_DB_ID=id-de-la-base-de-log
```

---

## Paso 8: Verificar la conexión

Reinicia los contenedores Docker:

```bash
docker compose down
docker compose up --build
```

Verifica que la conexión funciona:

```bash
curl http://localhost:8000/api/v1/notion/health
```

Deberías ver:
```json
{
  "status": "ok",
  "notion_connected": true,
  "tasks_db": "configured",
  "log_db": "configured"
}
```

---

## Paso 9: Configurar la vista Kanban en Notion

1. Abre la base de datos **FlowStep Tasks** en Notion
2. Haz clic en **"+ Add a view"** → **"Board"**
3. Agrupa por la propiedad **Status**
4. ¡Listo! Ahora tienes un tablero Kanban visual que se sincroniza con FlowStep AI

---

## Resumen de Variables de Entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `NOTION_API_TOKEN` | Token de la Integration | `secret_abc123...` |
| `NOTION_ROOT_PAGE_ID` | ID de la página raíz | `abc123de-f456-7890-...` |
| `NOTION_TASKS_DB_ID` | ID de la DB de tareas (auto) | `def456ab-...` |
| `NOTION_LOG_DB_ID` | ID de la DB de logs (auto) | `ghi789cd-...` |

---

## Solución de Problemas

### "Notion API returned 401"
- Verifica que el token en `.env` sea correcto y empiece con `secret_`
- Verifica que no haya espacios extra

### "Notion API returned 404"
- Verifica que compartiste la página con la Integration (Paso 4)
- Verifica que el Page ID sea correcto

### "Could not find database"
- Ejecuta el script de setup (Paso 7)
- Verifica que los IDs de las DBs estén en `.env`

### Las tareas no aparecen en Notion
- Verifica la conexión: `curl http://localhost:8000/api/v1/notion/health`
- Revisa los logs del backend: `docker compose logs backend`
