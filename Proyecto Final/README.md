# FlowStep AI — Agente de Productividad Personal con IA

> **Metodología:** Spec Driven Development (SDD)  
> **LLM Base:** Claude Opus 4.5 (Anthropic)  
> **Plataforma:** Desktop (Windows / macOS / Linux vía Docker)  
> **Equipo:** Juan Diego Camacho · Julian Andres Castaño · Santiago Santamaria Romero · Juan Sebastian Martelo

---

## 📋 Descripción del Proyecto

**FlowStep AI** es un agente de productividad personal que resuelve el problema de la **ceguera de contexto local** en los asistentes actuales. A diferencia de herramientas convencionales, FlowStep:

- 📝 **Recibe pendientes en lenguaje natural** — No necesitas estructurar nada
- 🤖 **Genera un plan diario priorizado con IA** — Analiza urgencia y esfuerzo automáticamente
- 🔍 **Verifica progreso real** — Lee tu sistema de archivos local vía MCP para confirmar completitud
- ✅ **Avanza solo con evidencia** — No marca tareas completadas hasta confirmar cambios reales

### Flujo de Alto Nivel

```
[FASE 1] TRIAGE          →  [FASE 2] ACOMPAÑAMIENTO         →  [FASE 3] CIERRE
Captura pendientes           Guía paso a paso                   Reporte de sesión
Evalúa urgencia/esfuerzo     Verifica entorno local (MCP)        Menú de salida
Genera Hoja de Ruta          Avanza solo con evidencia           Prepara siguiente sesión
Confirmación usuario         Alerta si hay bloqueo
```

---

## 🏗️ Arquitectura del Sistema

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
└──────────────────────────────────────────────────────────┘
```

**Componentes:**

| Componente | Responsabilidad |
|---|---|
| **Frontend (React)** | UI de sesión: entrada de tareas, Hoja de Ruta, progreso, reporte |
| **Backend API (FastAPI)** | Orquestación de sesiones, gestión de estado, validación |
| **OpenClaw Agent** | Core del agente: razonamiento, invocación MCP, control de flujo |
| **MCP Filesystem** | Acceso controlado al filesystem con allow-list estricta |
| **SQLite** | Persistencia local: sesiones, tareas, auditoría |
| **Claude API** | LLM: planificación, triage, resúmenes |

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| **Frontend** | React + Vite | 18+ / 5+ |
| **Estilos** | TailwindCSS | 3.x |
| **Backend** | FastAPI (Python) | 0.110+ |
| **Agent** | OpenClaw + MCP SDK | Latest |
| **LLM** | Claude API | claude-opus-4-5 |
| **DB** | SQLite + SQLAlchemy | 2.x |
| **Contenedores** | Docker + Docker Compose | 24+ |
| **Autenticación** | JWT (PyJWT) | 2.x |

---

## 🚀 Inicio Rápido

### Requisitos Previos

- **Docker Desktop** (versión 24+)
- **Git**
- **Cuenta en Anthropic** con API key válida

### Pasos de Instalación

1. **Clona el repositorio**
   ```bash
   git clone https://github.com/JSMT04/TecnologiasDisruptivas.git
   cd TecnologiasDisruptivas/Proyecto\ Final
   ```

2. **Configura las variables de entorno**
   ```bash
   cp .env.example .env
   ```
   Edita `.env` con tus valores:
   ```env
   ANTHROPIC_API_KEY=sk-ant-...
   JWT_SECRET=<string_aleatorio_256bit>
   MCP_ALLOW_LIST=/ruta/abs/proyecto1,/ruta/abs/proyecto2
   SESSION_TIMEOUT_MINUTES=480
   LOG_LEVEL=INFO
   ```

3. **Inicia los contenedores**
   ```bash
   docker compose up -d
   ```

4. **Accede a la aplicación**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Documentación API: http://localhost:8000/docs

---

## 📖 Funcionalidades Principales

### ✨ Fase 1: Triage

- Captura de pendientes en lenguaje natural
- Análisis automático de urgencia y esfuerzo
- Generación de plan diario priorizado
- Confirmación explícita del usuario antes de iniciar

### 🎯 Fase 2: Acompañamiento

- Guía paso a paso para cada tarea
- Verificación automática del filesystem (MCP)
- Avance controlado: solo con evidencia real
- Gestión de bloqueos y dependencias

### 📊 Fase 3: Cierre

- Reporte automático de sesión en Markdown
- Estadísticas de productividad
- Exportación y persistencia de datos
- Opciones de cierre: descanso, nuevo proyecto, salida

### 💾 Características Adicionales

- **Historial de sesiones** — Visualiza y continúa tareas pendientes
- **Configuración personalizable** — Adapta timeouts, temas y plantillas de proyectos
- **Auditoría completa** — Log inmutable de todas las operaciones del filesystem
- **Seguridad robusta** — JWT, allow-list de rutas, sanitización de inputs

---

## 🔐 Seguridad

- **Aislamiento en Docker** — Usuarios no-root, sin privilegios
- **Allow-list estricta** — MCP solo accede a directorios autorizados
- **Sin telemetría** — Datos nunca abandonan tu máquina (excepto prompts a Claude API)
- **Auditoría inmutable** — Todas las operaciones de filesystem se registran
- **API key segura** — Almacenada solo en `.env`, nunca expuesta al frontend

---

## 📁 Estructura del Proyecto

```
flowstep-ai/
├── docker-compose.yml          ← Punto de entrada único
├── .env.example               ← Plantilla de configuración
├── .gitignore                 ← Exclusiones (incluyendo .env)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                ← FastAPI entrypoint
│   ├── agent/                 ← OpenClaw core
│   ├── mcp/                   ← MCP client wrapper
│   ├── models/                ← SQLAlchemy models
│   └── routers/               ← API endpoints
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── pages/             ← Componentes de fases
│       └── components/
└── data/                      ← Volumen local (gitignored)
    ├── flowstep.db
    └── audit.log
```

---

## 🧪 Testing

### Tests Unitarios
```bash
docker compose exec backend pytest tests/unit/ -v
```

### Tests de Integración
```bash
docker compose exec backend pytest tests/integration/ -v
```

### Tests E2E
```bash
docker compose exec frontend npm run test:e2e
```

---

## 📚 Documentación Completa

Para detalles exhaustivos sobre:

- **Requerimientos funcionales y no funcionales** → `FLOWSTEP_AI_SPECS.md`
- **Especificaciones técnicas completas** → `FLOWSTEP_AI_SPECKIT.md`
- **API REST** → http://localhost:8000/docs (Swagger)
- **Modelos de datos** → `backend/models/`

---

## 🛠️ Desarrollo

### Variables de Entorno Requeridas

| Variable | Ejemplo | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | **Obligatoria** — API key de Anthropic |
| `JWT_SECRET` | `random_256_bit_string` | **Obligatoria** — Clave para firmar JWT |
| `MCP_ALLOW_LIST` | `/home/user/proyecto1,/home/user/proyecto2` | Rutas accesibles por MCP |
| `SESSION_TIMEOUT_MINUTES` | `480` | Duración máxima de sesión (minutos) |
| `LOG_LEVEL` | `INFO` | Nivel de logging (DEBUG/INFO/WARNING/ERROR) |

### Comandos Útiles

```bash
# Levanta todo en segundo plano
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f backend

# Detiene todos los contenedores
docker compose stop

# Ejecuta comandos en un contenedor
docker compose exec backend bash

# Limpia volúmenes (⚠️ borra base de datos local)
docker compose down -v
```

---

## 🤝 Contribuciones

Este es un proyecto del curso **Tecnologías Disruptivas**. Las contribuciones están enfocadas al equipo actual.

---

## ⚖️ Licencia

Proyecto académico — Derechos reservados por el equipo de desarrollo.

---

## 📞 Contacto & Soporte

- **Reportar bugs:** [GitHub Issues](https://github.com/JSMT04/TecnologiasDisruptivas/issues)
- **Preguntas técnicas:** Abre una discussion en el repositorio
- **Email:** Disponible en perfiles del equipo

---

## 📝 Notas Importantes

⚠️ **Antes de subir cambios:**
1. Nunca commites `.env` (está en `.gitignore`)
2. Asegúrate de que `audit.log` no se suba (ignorado)
3. Los archivos en `data/` son locales — no se sincronizan

---

**Última actualización:** 2026-05-14  
**Estado:** Desarrollo activo — Fase A en progreso
