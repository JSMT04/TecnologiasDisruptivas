# FlowStep AI — Especificaciones de Requerimientos
> Documento complementario al SPEC KIT v1.0  
> Para referencia rápida del equipo de desarrollo

---

## ÍNDICE

### Requerimientos Funcionales
- [RF-01 — Cómo el usuario ingresa sus tareas del día](#rf-01)
- [RF-02 — Cómo la IA analiza y prioriza las tareas](#rf-02)
- [RF-03 — Cómo se muestra y confirma el plan del día](#rf-03)
- [RF-04 — Cómo el agente guía al usuario tarea por tarea](#rf-04)
- [RF-05 — Cómo el sistema verifica que el trabajo realmente se hizo](#rf-05)
- [RF-06 — Cómo el usuario reporta que está bloqueado](#rf-06)
- [RF-07 — Cómo se genera el resumen al terminar la sesión](#rf-07)
- [RF-08 — Qué opciones tiene el usuario al cerrar la sesión](#rf-08)
- [RF-09 — Cómo el usuario revisa sesiones anteriores](#rf-09)
- [RF-10 — Cómo el usuario configura el sistema a su medida](#rf-10)

### Requerimientos No Funcionales
- [RNF-01 — Todo corre en Docker, sin excepción](#rnf-01)
- [RNF-02 — OpenClaw es el núcleo del agente](#rnf-02)
- [RNF-03 — El acceso al filesystem es controlado y restringido](#rnf-03)
- [RNF-04 — El sistema debe ser rápido en operaciones cotidianas](#rnf-04)
- [RNF-05 — Los datos del usuario no salen del computador](#rnf-05)
- [RNF-06 — Cada acción del agente sobre archivos queda registrada](#rnf-06)
- [RNF-07 — El sistema se recupera solo de errores comunes](#rnf-07)
- [RNF-08 — La API interna está protegida contra accesos no autorizados](#rnf-08)

---

## REQUERIMIENTOS FUNCIONALES

---

<a name="rf-01"></a>
## RF-01 — Cómo el usuario ingresa sus tareas del día
> *Entrada de pendientes en lenguaje natural sin estructura previa*

**Como** usuario,  
**quiero** abrir FlowStep AI y escribir mis pendientes del día en texto libre,  
**para** que el sistema los procese sin que yo tenga que organizarlos previamente.

### Entradas esperadas
- Texto libre por tarea, mínimo 3 caracteres, máximo 500 caracteres por tarea.
- Hasta 20 tareas por sesión.
- Nivel de urgencia manual opcional por tarea: Alta / Media / Baja.

### Salidas esperadas
- Lista de tareas parseadas, cada una con un ID único asignado.
- Confirmación visual de las tareas reconocidas antes de procesar.

### Reglas de negocio
- Si el texto contiene múltiples tareas separadas por salto de línea o coma, el sistema las separa automáticamente.
- Entradas vacías o compuestas solo de espacios son rechazadas con mensaje de error inline (no página de error ni excepción).
- El sistema no avanza a triage hasta que el usuario haya ingresado al menos una tarea válida.

---

<a name="rf-02"></a>
## RF-02 — Cómo la IA analiza y prioriza las tareas
> *Triage automático: urgencia, esfuerzo y orden sugerido por el agente*

**Como** sistema,  
**quiero** evaluar cada tarea con IA,  
**para** asignar prioridad objetiva basada en urgencia y esfuerzo estimado sin que el usuario tenga que pensar en eso.

### Entradas esperadas
- Lista de tareas validadas del RF-01.
- Contexto de sesión anterior si existe: tareas pospuestas o bloqueadas del día anterior.

### Salidas esperadas
Cada tarea etiquetada con:

| Campo | Valores posibles |
|---|---|
| `urgencia` | Alta / Media / Baja |
| `esfuerzo` | Bajo (≤30 min) / Medio (30–120 min) / Alto (>120 min) |
| `dependencias` | Lista de IDs de tareas que deben ir antes (puede ser vacía) |
| `tipo` | `archivo` · `código` · `web` · `comunicación` · `otro` |

- Tiempo total estimado de la sesión en minutos.
- Advertencia visible si el total estimado supera 8 horas.

### Reglas de negocio
- El modelo no puede clasificar más de 3 tareas como "Alta urgencia + Alto esfuerzo" simultáneamente.
- Si el total estimado supera 8 horas, el sistema advierte y sugiere qué tareas aplazar, pero no las elimina sin confirmación del usuario.
- La respuesta del LLM se valida contra el esquema JSON esperado antes de mostrarla; si falla la validación, se reintenta una vez antes de mostrar error.

---

<a name="rf-03"></a>
## RF-03 — Cómo se muestra y confirma el plan del día
> *Hoja de Ruta visual con edición manual y confirmación obligatoria antes de empezar*

**Como** usuario,  
**quiero** ver el plan del día propuesto por la IA y poder ajustarlo antes de comenzar,  
**para** que el orden refleje mis prioridades reales y no solo las de la IA.

### Entradas esperadas
- Output del RF-02 (tareas con triage).
- Ajustes manuales opcionales: reordenar tareas, editar estimación de esfuerzo, eliminar tarea.

### Salidas esperadas
- Hoja de Ruta visual ordenada con: orden de ejecución, título, urgencia, tipo, tiempo estimado.
- Botón explícito "Comenzar con este plan" para confirmar.
- Botón de edición por tarea individual (reordenar, modificar, eliminar).

### Reglas de negocio
- El sistema **no inicia la Fase 2 sin confirmación explícita** del usuario mediante el botón de confirmación.
- Todos los cambios manuales del usuario se persisten en SQLite antes de continuar.
- Si el usuario elimina todas las tareas, el botón de confirmación queda deshabilitado.

---

<a name="rf-04"></a>
## RF-04 — Cómo el agente guía al usuario tarea por tarea
> *Acompañamiento activo: instrucciones específicas y contextuales para cada tarea*

**Como** usuario,  
**quiero** recibir instrucciones claras para la tarea activa,  
**para** saber exactamente qué debo hacer sin tener que pensar en la estructura del trabajo.

### Entradas esperadas
- Tarea activa de la Hoja de Ruta.
- Estado del entorno si ya se hizo una verificación MCP previa en esa tarea.

### Salidas esperadas
- Descripción del paso actual (máx. 150 palabras).
- Instrucciones específicas según el `tipo` de tarea:

| Tipo | Instrucción generada |
|---|---|
| `archivo` | Ruta exacta donde debe crearse o modificarse el archivo |
| `código` | Descripción de qué debe existir o cambiar en el código |
| `web` | URL o recurso externo a consultar |
| `comunicación` | Borrador o checklist de la comunicación |
| `otro` | Pasos en lenguaje natural |

- Indicador de progreso visible: "Tarea 2 de 7".

### Reglas de negocio
- Para tareas tipo `archivo` o `código`, el botón "Marcar como completado" está **deshabilitado** hasta que la verificación MCP confirme el estado esperado (ver RF-05).
- Para tareas tipo `web`, `comunicación` y `otro`, el usuario puede marcar manualmente como completado sin verificación automática.
- El agente no salta a la siguiente tarea sin acción explícita del usuario.

---

<a name="rf-05"></a>
## RF-05 — Cómo el sistema verifica que el trabajo realmente se hizo
> *Verificación objetiva del entorno local vía MCP, sin pedirle al usuario que reporte*

**Como** sistema,  
**quiero** leer el filesystem del usuario usando MCP,  
**para** confirmar objetivamente que una tarea fue completada antes de avanzar.

### Entradas esperadas
- Ruta absoluta esperada del archivo o directorio (definida por el agente en RF-04).
- Tipo de verificación a realizar:

| Tipo | Descripción |
|---|---|
| `existencia` | ¿El archivo o carpeta existe en esa ruta? |
| `no_vacío` | ¿El archivo tiene contenido mayor a 0 bytes? |
| `modificado_hoy` | ¿El archivo fue modificado durante la sesión activa? |
| `sintaxis_json` | ¿El archivo es JSON parseable? |
| `sintaxis_html` | ¿El archivo tiene estructura HTML válida? |
| `sintaxis_python` | ¿El archivo compila sin errores de sintaxis Python? |

### Salidas esperadas
```json
{
  "verificado": true,
  "detalle": "Archivo encontrado, 2.4 KB, modificado hace 3 minutos",
  "timestamp": "2025-07-10T14:32:00Z"
}
```
- Si `verificado: false`: mensaje de bloqueo con sugerencia de acción al usuario.
- Si `verificado: true`: el botón "Avanzar a la siguiente tarea" se desbloquea.

### Reglas de negocio
- El MCP server **solo accede a rutas dentro del allow-list** configurado en `.env`. Cualquier ruta fuera retorna error `403 PATH_NOT_ALLOWED` y se registra en el log de auditoría.
- Durante la verificación, el agente **solo lee** — nunca escribe ni modifica archivos.
- La verificación ocurre **solo cuando el usuario presiona "Verificar ahora"**, nunca de forma automática en background salvo que `verificacion_auto: true` esté activado en la configuración.
- Las rutas de verificación son definidas por el agente a partir del contexto de la tarea, **nunca construidas directamente con texto libre del usuario**.

---

<a name="rf-06"></a>
## RF-06 — Cómo el usuario reporta que está bloqueado
> *Gestión de bloqueos: el agente ayuda a desatascarse o reorganiza el plan*

**Como** usuario,  
**quiero** poder reportar que estoy bloqueado en una tarea,  
**para** que el sistema me ayude a desbloquearme o reorganice el plan sin perder el progreso.

### Entradas esperadas
- Botón "Estoy bloqueado" en la vista de tarea activa.
- Descripción opcional del bloqueo en texto libre (máx. 300 caracteres).

### Salidas esperadas
- Sugerencias de desbloqueo contextuales generadas por el agente (2–3 opciones).
- Opción "Posponer al final de la lista" — la tarea se mueve al último lugar.
- Opción "Marcar como requiere ayuda externa" — la tarea se pausa sin contar como completada.

### Reglas de negocio
- Una tarea pospuesta puede reactivarse manualmente en cualquier momento desde la Hoja de Ruta.
- El bloqueo se registra en SQLite con timestamp y descripción del usuario.
- Las tareas marcadas como "requiere ayuda externa" aparecen en el reporte de cierre como pendientes, no como completadas ni como abandonadas.

---

<a name="rf-07"></a>
## RF-07 — Cómo se genera el resumen al terminar la sesión
> *Reporte de cierre: qué se hizo, qué cambió en el filesystem, métricas de la sesión*

**Como** usuario,  
**quiero** ver un resumen claro de lo que logré al finalizar,  
**para** tener trazabilidad real de mi productividad sin tener que construir el resumen yo mismo.

### Entradas esperadas
- Todas las tareas de la sesión con su estado final.
- Log de verificaciones MCP realizadas durante la sesión.

### Salidas esperadas
Reporte con las siguientes secciones:

| Sección | Contenido |
|---|---|
| Resumen | Total completadas / pospuestas / bloqueadas, tiempo de sesión, puntuación |
| Logros | Lista de tareas completadas con tipo y ruta verificada (si aplica) |
| Pendiente para mañana | Tareas pospuestas o bloqueadas |
| Cambios detectados en el sistema | Archivos y carpetas creados o modificados según MCP |
| Nota del agente | Observación breve y contextual |

- Puntuación de productividad: `(completadas / total) × 100` mostrada como porcentaje.
- Botón de exportación del reporte como archivo `.md` en la ruta configurada en RF-10.

### Reglas de negocio
- El reporte lo genera la IA con un máximo de 300 palabras totales.
- La exportación usa el MCP server para escribir el archivo en la ruta de reportes, que debe estar en el allow-list.
- Si la ruta de exportación no está configurada, el sistema ofrece copiarlo al portapapeles como alternativa.

---

<a name="rf-08"></a>
## RF-08 — Qué opciones tiene el usuario al cerrar la sesión
> *Menú de salida: cierre limpio, descanso o preparación del próximo proyecto*

**Como** usuario,  
**quiero** elegir qué sucede al terminar la sesión,  
**para** no tener que pensar en el cierre del entorno de trabajo.

### Opciones disponibles

**Opción 1 — Cerrar FlowStep AI**
- Cierra la aplicación limpiamente.
- Guarda el estado final en SQLite.

**Opción 2 — Iniciar descanso**
- Muestra un temporizador configurable entre 5 y 60 minutos.
- Al finalizar el temporizador, suena una alerta y FlowStep AI vuelve al inicio.

**Opción 3 — Preparar nuevo proyecto**

*Entradas esperadas:*
- Nombre del proyecto (texto libre, máx. 80 caracteres, sin caracteres especiales del OS).
- Plantilla de estructura: `web` · `data` · `genérico`.
- Ruta destino (debe estar en el allow-list).

*Salidas esperadas:*
- Carpetas y archivos base creados en el filesystem vía MCP.
- Confirmación con árbol visual de directorios resultante.
- Mensaje de error si la ruta no está en el allow-list o si ya existe una carpeta con ese nombre.

### Reglas de negocio
- La opción 3 usa escritura vía MCP: requiere que la ruta destino esté explícitamente en el allow-list.
- El nombre del proyecto se sanitiza antes de usarse como nombre de carpeta (sin `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`).
- Si ya existe una carpeta con ese nombre en la ruta, el sistema pregunta si sobreescribir o usar nombre alternativo.

---

<a name="rf-09"></a>
## RF-09 — Cómo el usuario revisa sesiones anteriores
> *Historial de sesiones: continuidad del trabajo y trazabilidad histórica*

**Como** usuario,  
**quiero** ver mis sesiones anteriores,  
**para** poder continuar tareas pendientes o revisar mi historial de productividad.

### Entradas esperadas
- Filtro por rango de fechas (desde / hasta).

### Salidas esperadas
- Lista de sesiones con: fecha, duración, tareas totales, completadas, puntuación.
- Vista de detalle expandible por sesión con la lista completa de tareas y sus estados.
- Botón "Continuar tareas pendientes" por sesión — carga las tareas pospuestas y bloqueadas como base de una nueva sesión.

### Reglas de negocio
- Máximo 90 días de historial almacenado en SQLite local.
- El historial **no se sincroniza** a ningún servidor externo.
- Al cargar tareas de una sesión anterior, estas se tratan como tareas nuevas con contexto previo — el usuario puede editarlas antes de confirmar.

---

<a name="rf-10"></a>
## RF-10 — Cómo el usuario configura el sistema a su medida
> *Panel de configuración: personalización del comportamiento del agente y el entorno*

**Como** usuario,  
**quiero** ajustar los parámetros del sistema,  
**para** adaptarlo a mi flujo de trabajo sin tocar código ni archivos de configuración manualmente.

### Parámetros configurables

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `mcp_allow_list` | lista de rutas absolutas | `[]` | Carpetas que el agente puede leer/escribir |
| `session_timeout` | entero (minutos) | `480` | Tiempo máximo de sesión activa antes de cerrar automáticamente |
| `verificacion_auto` | booleano | `false` | Si MCP verifica archivos en background sin acción del usuario |
| `exportar_reporte_ruta` | ruta absoluta | `~/flowstep/reportes` | Carpeta destino para reportes de cierre |
| `plantilla_proyecto_default` | enum | `genérico` | Plantilla predeterminada para RF-08 opción 3 |
| `tema_ui` | enum | `oscuro` | `oscuro` / `claro` |

### Salidas esperadas
- Formulario visual con los parámetros actuales cargados.
- Guardado inmediato al confirmar cambios.
- Mensaje de confirmación o error inline por campo.

### Reglas de negocio
- Los cambios en `mcp_allow_list` requieren reinicio del servicio MCP (el sistema lo notifica y ofrece reiniciar desde la UI).
- Cada ruta agregada al `mcp_allow_list` se valida: debe existir en el host antes de ser aceptada. Si no existe, se rechaza con error claro.
- La configuración se almacena en `config.json` local, **nunca en la base de datos**.
- El archivo `config.json` no debe commitearse al repositorio (incluido en `.gitignore`).

---

---

## REQUERIMIENTOS NO FUNCIONALES

---

<a name="rnf-01"></a>
## RNF-01 — Todo corre en Docker, sin excepción
> *Portabilidad y aislamiento garantizados mediante contenedores*

- Todo el sistema (frontend, backend, MCP server) debe ejecutarse dentro de contenedores Docker.
- `docker-compose.yml` es el **único punto de arranque** del sistema. No debe haber instrucciones para correr servicios fuera de Docker.
- Comandos de uso:
  - Primera vez: `docker compose up --build`
  - Sesiones siguientes: `docker compose up`
- Los contenedores **no corren como root**. Cada `Dockerfile` define un usuario con UID 1000.
- El socket de Docker del host no se monta ni expone a ningún contenedor de la aplicación.
- Los puertos solo se exponen en `127.0.0.1` (localhost), nunca en `0.0.0.0`.

---

<a name="rnf-02"></a>
## RNF-02 — OpenClaw es el núcleo del agente
> *OpenClaw orquesta toda la inteligencia y las herramientas del sistema*

- OpenClaw actúa como el framework de orquestación del agente: recibe las instrucciones, razona y decide qué herramientas MCP invocar.
- Todas las llamadas al LLM (Claude API) pasan a través de OpenClaw, **nunca directamente desde el frontend** ni desde rutas del backend que omitan el agente.
- El agente mantiene el estado de la sesión en memoria durante la ejecución y lo persiste en SQLite al finalizar cada tarea completada o al detectar un cambio de estado.
- La configuración de herramientas MCP disponibles para el agente se define en el arranque; no se agregan herramientas en tiempo de ejecución.

---

<a name="rnf-03"></a>
## RNF-03 — El acceso al filesystem es controlado y restringido
> *El MCP server opera con allow-list estricta; nada fuera de ella es accesible*

- El MCP server solo puede acceder a rutas explícitamente listadas en `MCP_ALLOW_LIST` en el archivo `.env`.
- **Ninguna ruta fuera del allow-list puede ser leída ni escrita**, sin excepción.
- Las rutas de sistema operativo están implícitamente prohibidas: `/etc`, `/sys`, `/root`, `/usr`, `C:\Windows`, `C:\Program Files`, entre otras.
- Las herramientas habilitadas en el MCP server son únicamente:
  - `read_file` — solo lectura
  - `list_directory` — solo lectura
  - `get_file_info` — solo metadatos
  - `write_file` — solo escritura en allow-list, solo en operaciones explícitas (reporte y estructura de proyecto)
  - `create_directory` — solo en allow-list, solo en RF-08 opción 3
- Las herramientas `move_file`, `delete_file`, `execute_command` y búsqueda recursiva desde raíz están **deshabilitadas**.
- Toda operación del MCP (exitosa o denegada) se registra en el audit log (ver RNF-06).

---

<a name="rnf-04"></a>
## RNF-04 — El sistema debe ser rápido en operaciones cotidianas
> *Tiempos de respuesta aceptables para no interrumpir el flujo de trabajo del usuario*

| Operación | Tiempo máximo aceptable |
|---|---|
| Triage de hasta 20 tareas (RF-02) | ≤ 10 segundos |
| Verificación MCP de existencia o tamaño (RF-05) | ≤ 2 segundos |
| Carga inicial de la UI en localhost | ≤ 3 segundos |
| Generación del reporte de cierre (RF-07) | ≤ 8 segundos |

- El sistema está diseñado para **una sola sesión activa simultánea** por instancia (uso personal, no multiusuario).
- Las llamadas a Claude API se realizan de forma asíncrona; la UI muestra un indicador de carga durante la espera.

---

<a name="rnf-05"></a>
## RNF-05 — Los datos del usuario no salen del computador
> *Privacidad garantizada: solo los prompts necesarios van a la API externa*

- Ningún dato de tareas, rutas, historial ni archivos del usuario se envía a servidores externos, **excepto los prompts de inferencia enviados a Claude API**.
- Los prompts enviados a Claude API **no incluyen contenido de archivos del usuario** — solo metadatos: nombre, extensión, tamaño en bytes, fecha de última modificación.
- El historial de sesiones se almacena únicamente en SQLite local en el directorio `data/` del proyecto.
- No hay telemetría, analytics, ni tracking de ningún tipo en el sistema.
- La API key de Anthropic se almacena solo en el archivo `.env` local, **nunca en el código fuente ni en la base de datos**.

---

<a name="rnf-06"></a>
## RNF-06 — Cada acción del agente sobre archivos queda registrada
> *Auditabilidad completa de operaciones MCP para seguridad y trazabilidad*

- Cada operación del MCP server genera una entrada inmutable en `audit.log` con el formato:
  ```
  [ISO8601] [OPERACIÓN] [RUTA] [RESULTADO] [SESIÓN_ID]
  ```
  Ejemplo:
  ```
  [2025-07-10T14:32:01Z] [READ] [/home/user/proyecto/main.py] [OK] [sess_abc123]
  [2025-07-10T14:33:15Z] [READ] [/etc/passwd] [DENIED] [sess_abc123]
  ```
- Las operaciones registradas son: `READ`, `WRITE`, `LIST`, `CREATE_DIR`, `DENIED`.
- El log es de **solo-append**: no puede borrarse ni editarse desde la UI.
- Los logs se rotan diariamente con retención máxima de 30 días.
- El archivo `audit.log` está en el directorio `data/`, montado como volumen Docker persistente.

---

<a name="rnf-07"></a>
## RNF-07 — El sistema se recupera solo de errores comunes
> *Resiliencia ante fallos de red, API y filesystem sin perder el estado de la sesión*

**Fallo de Claude API:**
- El sistema reintenta automáticamente hasta 3 veces con backoff exponencial (1s, 2s, 4s).
- Si los 3 intentos fallan, muestra error claro con botón "Reintentar manualmente".
- El estado de la sesión no se pierde durante el error.

**Fallo de lectura MCP (permisos del OS):**
- Si el MCP server no puede leer un archivo por permisos del sistema operativo (no por allow-list), informa al usuario con el error específico.
- Se desbloquea el avance manual para que el usuario pueda confirmar la tarea sin verificación automática.

**Caída del backend:**
- El frontend muestra un estado "Reconectando..." y reintenta la conexión cada 5 segundos.
- Al reconectar, el estado de la sesión se recarga desde SQLite automáticamente.
- El usuario no pierde el progreso de tareas ya marcadas.

---

<a name="rnf-08"></a>
## RNF-08 — La API interna está protegida contra accesos no autorizados
> *Seguridad de la capa de comunicación frontend-backend*

- Todos los endpoints del backend requieren un JWT válido en el header `Authorization: Bearer <token>`.
- El único endpoint sin autenticación es `GET /health` (para el healthcheck de Docker).
- El JWT se genera al iniciar una nueva sesión y expira según el valor de `SESSION_TIMEOUT_MINUTES`.
- La API key de Anthropic **nunca se expone al frontend** bajo ninguna circunstancia.
- **CORS** configurado exclusivamente para `http://localhost:3000`.
- **Rate limiting:** máximo 60 requests por minuto por sesión activa. Superar el límite retorna `429 Too Many Requests`.
- **Sanitización de inputs:** todas las entradas de texto del usuario pasan por strip de HTML y validación de longitud antes de ser procesadas por el agente.
- **Protección contra path traversal:** cualquier ruta que contenga `../`, `..\`, o que sea absoluta y no esté en el allow-list es rechazada con `400 Bad Request` antes de llegar al MCP server.

---

*FlowStep AI — Specs v1.0 · Documento complementario al SPEC KIT principal*
