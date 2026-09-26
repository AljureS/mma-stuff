# MMA Fight Predictor - Guía del Proyecto

> **⚠️ IMPORTANTE - DOCUMENTACIÓN SINCRONIZADA**
>
> Este archivo `CLAUDE.md` es la fuente única de verdad del proyecto.
> **CUALQUIER CAMBIO a cualquier archivo del proyecto (código, configuración, estructura, dependencias, endpoints, datos) DEBE reflejarse inmediatamente en este archivo.**
>
> Esta documentación describe el estado REAL del código, distinguiendo explícitamente entre lo **implementado** y lo que es **placeholder/simulado**. Al actualizar, mantén esa distinción.

## ¿Qué es este proyecto?

Sistema de predicción de peleas de MMA: una API FastAPI que compara las estadísticas de dos peleadores, predice el ganador con un modelo XGBoost y genera un análisis cualitativo con LLM (OpenAI con fallback a Ollama). Incluye un frontend web estático y un scraper de UFCStats que alimenta la base de datos de peleadores.

## Estado Actual (leer antes de tocar código)

Proyecto en **fase de desarrollo/prototipo**, tras el **refactor de limpieza 2026-07-01** (ver `tasks/todo.md`): se eliminaron ~1,600 LOC de código muerto/placeholder (ml_system.py, deployment_setup.sh, database_schema.sql, endpoints falsos, 8 dependencias sin uso) y se corrigieron los bugs de cache key y del buscador.

**Implementado y funcional:**
- API FastAPI (`api/main.py`, 590 LOC) con cache Redis (key normalizada) y validación Pydantic — 5 endpoints, todos reales
- Cliente LLM con fallback OpenAI → Ollama, reintentos, circuit breakers (`api/llm_client.py`) + 15 tests unitarios
- Scraping automático de UFCStats cuando un peleador no existe en el CSV o sus datos tienen >7 días (`get_fighter_data` en `main.py` → `MMADataCollector.search_and_scrape_fighter`)
- Frontend HTML/JS/Tailwind que consume la API (rediseño Fight Night 2026-07)

**Placeholder / simulado (lo que queda):**
- **El modelo ML actual es dummy**: `models/mma_prediction_model.pkl` fue generado por `scripts/setup_dev_data.py` entrenando XGBoost (`n_estimators=100`) sobre **datos aleatorios**. Las probabilidades que devuelve `/predict` no tienen valor predictivo real.
- `main.py` calcula solo 10 features reales y rellena con ceros hasta 16 (ver sección Features). **El padding NO es borrable**: el pkl espera exactamente 16 inputs.

**Issues conocidos:**
- El scraper de UFCStats devuelve 0 filas (detectado 2026-07-01: el HTML del sitio cambió o bloquea requests). El fallback a datos stale del CSV funciona por diseño, así que la API opera normal; arreglar el parser es pendiente.
- Redis (`localhost:6379`) y uvicorn (`0.0.0.0:8000`) siguen hardcodeados (no leen el .env).

**Eliminado en el refactor 2026-07-01** (recuperable vía git si algún día se implementa de verdad): `api/ml_system.py`, `database_schema.sql`, `scripts/deployment_setup.sh`, `POST /retrain` (no-op), `GET /events/upcoming` (hardcodeado), `GET /analytics/*` ×2 (hardcodeados), `get_betting_insights()` (odds falsas), `get_recent_form()`/`get_current_ranking()` (valores inventados), deps psycopg2/structlog/python-jose/passlib/selenium/webdriver-manager/lxml/python-multipart, y el JS inline duplicado del frontend.

## Estructura Real del Proyecto

```
mma-stuff/
├── CLAUDE.md                      # Este archivo (fuente de verdad)
├── .claude/
│   ├── agents/                    # Subagentes del refactor: slop-auditor, backend-refactorer,
│   │                              #   mma-ui-builder, stack-verifier (ver "Tooling de Refactor")
│   └── skills/                    # Skills: mma-run-stack, slop-audit, mma-ui-theme,
│                                  #   refactor-verify, sync-claude-md
├── tasks/
│   ├── todo.md                    # Plan maestro del refactor 2026-07 (checkable) + inventario de slop
│   ├── lessons.md                 # Correcciones del usuario y reglas aprendidas
│   └── baselines/                 # Respuestas de referencia pre-refactor (gitignored)
├── README.md                      # Entry point conciso (reescrito 2026-07-01)
├── README_LLM.md                  # Doc del sistema LLM
├── test_scraping.py               # Script manual de prueba del scraper
├── api/
│   ├── main.py                    # Servidor FastAPI (toda la API + feature engineering, 590 LOC)
│   ├── llm_client.py              # Cliente LLM con fallback OpenAI → Ollama
│   ├── requirements.txt           # 16 dependencias Python (podado 2026-07-01)
│   └── .env                       # Variables de entorno (gitignored, NO commitear)
├── scripts/
│   ├── data_collection.py         # MMADataCollector (scraping UFCStats, 259 LOC tras poda)
│   └── setup_dev_data.py          # Genera modelo dummy + CSV con 20 peleadores seed
├── data/
│   └── fighters_complete.csv      # Base de datos de peleadores (~37 filas, crece con scraping)
├── models/
│   └── mma_prediction_model.pkl   # Modelo XGBoost (actualmente dummy)
├── frontend/
│   ├── index.html                 # UI Fight Night (Tailwind CDN, Chart.js CDN, Font Awesome CDN)
│   ├── index.js                   # Lógica del cliente (API_BASE_URL = http://localhost:8000)
│   └── styles.css                 # Estilos custom del tema
└── tests/
    ├── __init__.py
    └── test_llm_client.py         # 15 tests del cliente LLM (pytest + pytest-asyncio)
```

Borrados en el refactor 2026-07-01: `ARCHITECTURE.md`, `IMPLEMENTATION_SUMMARY.md`, `database_schema.sql`, `api/ml_system.py`, `scripts/deployment_setup.sh`, `dump.rdb`. No existen `data/fight_history.csv` ni `data/training_data.csv` (mencionados en versiones antiguas de esta doc).

## Componente 1: API Backend (`api/main.py`)

### Endpoints

| Endpoint | Estado | Descripción |
|---|---|---|
| `GET /` | Real | Health check: estado, modelo cargado, conteo de peleadores |
| `POST /predict` | Real (modelo dummy) | Predicción de pelea con cache, features y análisis LLM |
| `GET /fighter/{name}` | Real | Stats del CSV (NaN→None); `ranking` sale de la columna `ranking` del CSV (null si falta); ya no existe `recent_form` |
| `GET /search/fighters/{query}` | Real | Búsqueda fuzzy (`str.contains`, case-insensitive) sobre el CSV, `limit` default 10. Fix 2026-07-01: sanitiza NaN (antes devolvía 500) |
| `GET /health/llm` | Real | Estado de proveedores LLM y circuit breakers |

Eliminados 2026-07-01 (devuelven 404): `POST /retrain`, `GET /events/upcoming`, `GET /analytics/model-performance`, `GET /analytics/betting-roi`.

### Flujo de `/predict`

1. Verificar cache Redis con **key normalizada** `prediction:{min}:{max}` (nombres `strip().lower()` ordenados; TTL 3600s). Hit → si el orden de peleadores del request difiere del cacheado, `_swap_cached_prediction()` intercambia nombres/probabilidades y **niega los `key_factors`** (son diferencias a−b) antes de responder.
2. `get_fighter_data()` para cada peleador (ver "Datos de peleadores" abajo). Si alguno no se encuentra ni se puede scrapear → 404 con nombres faltantes.
3. `engineer_fight_features()` genera el vector de 16 posiciones.
4. `prediction_model.predict_proba([features])` — **convención: `probabilities[1]` = probabilidad de que gane fighter_a**.
5. Si `include_llm_analysis=true` (default): análisis LLM en español (max_tokens=800, temperature=0.7, prompt limita a ~700 palabras).
6. Respuesta `FightPredictionResponse` (sin `betting_insights` desde 2026-07-01) + cache en Redis por 1 hora.

Helpers de sanitización: `_nan_to_none()` y `_sanitize_csv_record()` (main.py) — aplicar a TODA respuesta construida desde filas del CSV (tiene NaN).

### Datos de peleadores con auto-scraping (`get_fighter_data`)

- Busca en el CSV en memoria: primero match exacto por `name`, luego fuzzy (`str.contains`).
- Si el peleador existe y `last_updated` tiene **menos de 7 días** → usa el dato cacheado.
- Si no existe o está stale → scrapea UFCStats vía `MMADataCollector.search_and_scrape_fighter()`, actualiza/agrega la fila al CSV con `last_updated` (ISO), y recarga `fighter_database` en memoria.
- Si el scraping falla → fallback a los datos viejos (si existían).

### Features del modelo (las que se calculan DE VERDAD)

`engineer_fight_features()` en `main.py` produce, en este orden:

1. `height_diff` (default por valor faltante: 180 cm)
2. `reach_diff` (default 180 cm)
3. `age_diff` (default 30)
4. `win_rate_diff` (wins / max(total_fights, 1))
5. `experience_diff` (total de peleas)
6. `striking_accuracy_diff` (default 50)
7. `striking_defense_diff` (default 50)
8. `takedown_accuracy_diff` (default 30)
9. `takedown_defense_diff` (default 70)
10. `title_fight` (1.0 / 0.0)
11–16. **Relleno con ceros** hasta completar 16 posiciones

`safe_get()` maneja None/NaN/no-convertibles con los defaults indicados. Las 16 features "completas" (con scores compuestos, forma reciente, calidad de oponentes, style matchup) están documentadas al final de "Componente 3" — implementarlas en la API es trabajo pendiente (junto con entrenar el modelo real).

`get_key_factors()` reporta los 5 factores con |valor| > 0.1 de las primeras 10 features.

### Infraestructura del servidor

- Redis: **hardcodeado** `localhost:6379` db 0 (la variable `REDIS_URL` del .env no se lee).
- Uvicorn: **hardcodeado** `0.0.0.0:8000` (las variables `API_HOST`/`API_PORT` no se leen). Reload activo si se pasa `--reload` o existe env `DEBUG`.
- CORS: `allow_origins=["*"]` (restringir en producción).
- Startup: carga `models/mma_prediction_model.pkl` y `data/fighters_complete.csv` con rutas relativas a la raíz del proyecto (`Path(__file__).parent.parent`).
- `main.py` agrega `scripts/` al `sys.path` para importar `data_collection`.

## Componente 2: Cliente LLM (`api/llm_client.py`)

Fallback OpenAI → Ollama con reintentos y circuit breakers.

```
FastAPI → LLMClient (singleton, get_llm_client())
              ├── 1° OpenAI (AsyncOpenAI, chat.completions, default gpt-4o-mini)
              └── 2° Ollama local (default qwen2.5:7b, POST {OLLAMA_URL}/api/generate)
```

**Flujo de decisión:**
1. OpenAI primero (si hay `OPENAI_API_KEY` y su circuit breaker está cerrado):
   - `RateLimitError` / `APITimeoutError` → **sin reintento**, fallback inmediato a Ollama
   - `APIError` → hasta 3 reintentos con backoff exponencial (1s, 2s, 4s), luego fallback
   - Cualquier otra excepción → fallback
2. Ollama: hasta 3 reintentos con el mismo backoff. `fallback_used=True` si OpenAI estaba disponible.
3. Ambos fallan → `LLMResponse` con mensaje de error genérico (nunca lanza excepción al caller).
4. Ambos circuit breakers abiertos → mensaje "servicio no disponible".

**Detalles de la llamada OpenAI:** el system prompt va como primer mensaje (`{"role": "system", ...}`, se omite si está vacío), se usa `max_completion_tokens` (no el deprecado `max_tokens`), y el timeout se pasa explícito al cliente (el default del SDK es 600s y rompería el fast-fallback). `tokens_used` viene de `usage.total_tokens`.

**Circuit breakers:** OpenAI abre tras 5 fallas consecutivas (timeout 60s); Ollama tras 3 (timeout 30s). Pasado el timeout entran en `half_open` para probar recuperación.

**Timeouts (ojo, no es simétrico):** en `get_llm_client()` el timeout de OpenAI está fijo en 30s; `LLM_TIMEOUT` del .env aplica **solo a Ollama** (los modelos locales son más lentos). Si se construye `LLMClient` a mano sin `ollama_timeout_seconds`, Ollama usa 3× el timeout de OpenAI.

**Otros detalles:** sin `OPENAI_API_KEY` el cliente opera en modo solo-Ollama (warning en logs). `health_check()` reporta estado de breakers (keys `openai` y `ollama`) y prueba `GET {OLLAMA_URL}/api/tags` con timeout de 5s. `force_provider=LLMProvider.OLLAMA` salta OpenAI. `LLMResponse` incluye provider, model, latency_ms, tokens_used y fallback_used (se loguea en cada análisis).

**Costo (precios junio 2026):** gpt-4o-mini cuesta $0.15/1M tokens input y $0.60/1M output → un análisis típico (~320 in + 800 out) cuesta ≈ $0.0005, o ~$0.60 por cada 1,000 predicciones. Cambiar de modelo es editar `OPENAI_MODEL` en el .env.

## Componente 3: Recolección de Datos (`scripts/data_collection.py`)

Clase `MMADataCollector` (requests + BeautifulSoup, 259 LOC tras la poda 2026-07-01). Cadena de producción:

- `search_and_scrape_fighter(name)` — **el método que usa la API** (vía `get_fighter_data` en main.py, importado con hack de `sys.path`). Busca en UFCStats por la inicial del apellido (`?char=X&page=all`), match fuzzy case-insensitive, parsea altura/peso/alcance/stance/récord, y llama internamente a `get_fighter_detailed_stats`. Infiere `weight_class` por peso en libras. Defaults si faltan stats: striking_accuracy 50, striking_defense 55, takedown_accuracy 40, takedown_defense 70, age 30.
- `get_fighter_detailed_stats(profile_url)` — stats del perfil (striking/takedown accuracy/defense vía `_normalize_stat_name`/`_parse_stat_value`) + fight history. **Es producción, NO borrar** (un audit lo marcó muerto por error; la llamada está dentro de `search_and_scrape_fighter`).
- Parsers: `_parse_height`, `_parse_weight`, `_parse_reach`, `_infer_weight_class`.

Eliminados 2026-07-01 (solo eran alcanzables desde un `main()` que nunca corría, o desde nadie): `scrape_ufc_stats`, `scrape_sherdog_rankings`, `scrape_tapology_events`, `get_betting_odds_historical`, `get_social_sentiment` + helpers Reddit/Twitter, `save_data`, `main()`, imports de selenium/pandas/time/json.

**Issue conocido:** el scraping devuelve 0 filas desde ~2026-07 (UFCStats cambió HTML o bloquea). La API degrada a datos stale del CSV sin romperse.

Prueba manual del scraper: `python test_scraping.py` (busca a Mateusz Gamrot).

**Las 16 features objetivo del modelo real** (heredadas del borrado `ml_system.py`, para cuando se entrene en serio): `height_diff`, `reach_diff`, `age_diff`, `experience_diff`, `win_rate_diff`, `finish_rate_diff`, `takedown_acc_diff`, `takedown_def_diff`, `sig_str_acc_diff`, `sig_str_def_diff`, `cardio_score_diff`, `power_score_diff`, `grappling_score_diff`, `recent_form_diff`, `opponent_quality_diff`, `style_matchup_score`. Hiperparámetros de referencia: XGBClassifier `n_estimators=1000`, `learning_rate=0.01`, `max_depth=6`, `subsample=0.8`, `colsample_bytree=0.8`, split 80/20, early stopping 50.

## Componente 4: Frontend (`frontend/`)

UI rediseñada 2026-07-01 con el design system **Fight Night** (ver skill `mma-ui-theme`: tokens arena/corner/gold/canvas, Barlow Condensed + Inter por Google Fonts, corners rojo/azul, oro solo para title fight).

- `index.html` (258 LOC): header cartelera, matchup con corner rojo | VS | corner azul, opciones (peso/evento/checkbox title fight con badge dorado), `resultsSection` (banner de ganador con glow de corner, chart, key factors, análisis de esquina), `loadingModal` con octágono girando. Config de Tailwind inline con los tokens. **El bloque JS inline duplicado fue eliminado** — `index.js` es la única fuente (antes el inline era la copia viva: el externo moría en parse por redeclarar `API_BASE_URL`).
- `index.js` (271 LOC): `API_BASE_URL = 'http://localhost:8000'`. Consume SOLO `POST /predict` (siempre `include_llm_analysis: true`) y `GET /search/fighters/` (debounce 500ms). Doughnut con colores de corner, key factors con iconos y color según a quién favorecen (signo del diff, ver skill), banner de ganador (`winnerBanner`/`titleBeltNote` — title fight se toma del request, no viene en la respuesta). Patrón destroy-antes-de-recrear del chart.
- `styles.css` (192 LOC): componentes custom del tema — spinner octágono (clip-path + conic-gradient), glows de ganador por corner/oro, clases dinámicas que el JS aplica (`.winner-*`, `.factor-*`; van aquí y no como utilidades Tailwind por el CDN).

Los IDs del DOM son contrato con `index.js` — la lista completa vive en la skill `mma-ui-theme` (reglas de compatibilidad).

## Datos

**`data/fighters_complete.csv`** — única fuente de datos de la API. Columnas:
`name, wins, losses, draws, height, reach, age, weight_class, ranking, striking_accuracy, striking_defense, takedown_accuracy, takedown_defense, last_updated, weight, stance, fight_history`

Las últimas 4 columnas las agrega el scraper. Alturas/alcances en cm, peso en lbs. Se siembra con 20 peleadores vía `setup_dev_data.py` y crece automáticamente con el auto-scraping (~37 filas actualmente). **La API escribe en este archivo en runtime** (por eso aparece modificado en git).

**`models/mma_prediction_model.pkl`** — XGBoost serializado con pickle. El actual es dummy (ver Estado Actual). Para regenerarlo: `python scripts/setup_dev_data.py` desde la raíz del proyecto. OJO: cargar el pkl requiere `scikit-learn` instalado (es un XGBClassifier con wrapper sklearn) — esa dependencia NO es borrable aunque nada la importe directamente.

**`tasks/baselines/`** — respuestas de referencia capturadas antes del refactor (predict = 0.7760478854179382 para Jon Jones vs Stipe Miocic sin LLM). Gitignored; usadas por la skill `refactor-verify` para checks de paridad.

## Variables de Entorno (`api/.env`, gitignored)

Leídas realmente por el código:

```bash
OPENAI_API_KEY=sk-proj-...                    # Sin ella: modo solo-Ollama
OPENAI_BASE_URL=                              # Opcional, base URL custom (comentada en el .env actual)
OPENAI_MODEL=gpt-4o-mini                      # Default si no se define
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
LLM_MAX_RETRIES=3
LLM_TIMEOUT=180                               # Aplica SOLO a Ollama (OpenAI fijo en 30s)
DEBUG=                                        # Si existe, uvicorn corre con reload
```

Presentes en `.env` pero **no leídas por el código** (reservadas para producción): `DATABASE_URL`, `REDIS_URL`, `API_HOST`, `API_PORT`, `SECRET_KEY`, `LOG_LEVEL`, `ENVIRONMENT`. No existe `.env.example` (está gitignored); para reproducir el .env usa la lista de arriba.

## Cómo Ejecutar

```bash
# 1. Dependencias (hay un venv/ en la raíz)
cd api && pip install -r requirements.txt

# 2. Servicios
redis-server                      # obligatorio (la API asume localhost:6379)
ollama serve                      # opcional (fallback LLM)
ollama pull qwen2.5:7b

# 3. Datos de desarrollo (si faltan modelo o CSV)
python scripts/setup_dev_data.py  # desde la raíz del proyecto

# 4. API
cd api && python main.py          # http://localhost:8000 (docs en /docs)

# 5. Verificar
curl http://localhost:8000/            # health general
curl http://localhost:8000/health/llm  # estado LLM

# 6. Frontend: servir frontend/ con cualquier servidor estático
#    p. ej.: python -m http.server 3000 --directory frontend
```

(El script de deployment Linux `deployment_setup.sh` se eliminó 2026-07-01: configuraba PostgreSQL/Nginx/Systemd que el código no usa.)

## Tests

```bash
pytest tests/test_llm_client.py -v   # 15 tests: circuit breaker, fallback, reintentos, health check
python test_scraping.py              # prueba manual del scraper contra UFCStats (red real)
```

Los tests del LLM mockean OpenAI y aiohttp (pytest-asyncio + pytest-mock). No hay tests para `main.py` ni para el scraper — su única verificación es ejecución real (ver skill `refactor-verify`).

## Stack Tecnológico

- **Backend:** Python, FastAPI 0.104, uvicorn, Pydantic 2.5, pandas, numpy, XGBoost 1.7, scikit-learn (requerida para deserializar el pkl), redis-py, aiohttp, requests + BeautifulSoup4, openai 2.41, python-dotenv — 16 deps totales (podadas de 24 el 2026-07-01)
- **Frontend:** HTML/JS vanilla + TailwindCSS, Chart.js y Font Awesome por CDN
- **Infra activa:** Redis (cache). Toda la infra declarada-pero-no-conectada (PostgreSQL, Nginx, Docker, Supervisor) se eliminó en el refactor 2026-07-01.
- **LLM:** OpenAI gpt-4o-mini (primario) + Ollama Qwen2.5:7b (fallback local)

## Trabajo Pendiente Prioritario

1. **Entrenar un modelo real**: el pkl actual es dummy. Requiere construir un dataset de peleas históricas (no existe `training_data.csv`). Las 16 features objetivo e hiperparámetros de referencia están documentados al final de "Componente 3".
2. **Cerrar la brecha de features**: `main.py` calcula 10 de 16 features; implementar los scores compuestos, forma reciente, calidad de oponentes y style matchup en el flujo de la API (junto con el punto 1).
3. **Arreglar el parser del scraper**: UFCStats devuelve 0 filas desde ~2026-07 (cambio de HTML o bloqueo); hoy la API vive de los datos stale del CSV.
4. Parametrizar Redis y uvicorn por variables de entorno (hoy hardcodeados).

## Workflow Orchestration (cómo trabajar en este proyecto)

### 1. Plan Mode por defecto
- Entra en plan mode para CUALQUIER tarea no trivial (3+ pasos o decisiones de arquitectura).
- Si algo se desvía, DETENTE y re-planea de inmediato — no sigas empujando.
- Usa plan mode también para pasos de verificación, no solo para construir.
- Escribe specs detalladas por adelantado para reducir ambigüedad.

### 2. Estrategia de subagentes
- Usa subagentes liberalmente para mantener limpio el contexto principal.
- Delega investigación, exploración y análisis paralelo a subagentes.
- Para problemas complejos, escala con más cómputo vía subagentes.
- Un enfoque por subagente para ejecución concentrada.

### 3. Ciclo de auto-mejora
- Tras CUALQUIER corrección del usuario: registra el patrón en `tasks/lessons.md`.
- Escribe reglas para ti mismo que prevengan el mismo error.
- Itera sin piedad sobre esas lecciones hasta que la tasa de errores baje.
- Revisa las lecciones al inicio de cada sesión de este proyecto.

### 4. Verificación antes de dar por terminado
- Nunca marques una tarea como completa sin demostrar que funciona.
- Compara el comportamiento entre `main` y tus cambios cuando aplique.
- Pregúntate: "¿Un staff engineer aprobaría esto?"
- Corre los tests (`pytest tests/test_llm_client.py -v`), revisa logs, demuestra correctitud. Para cambios en la API, verifica contra el servidor corriendo (`curl http://localhost:8000/`).

### 5. Exigir elegancia (con balance)
- Para cambios no triviales: pausa y pregunta "¿hay una forma más elegante?"
- Si un fix se siente hacky: "Sabiendo todo lo que sé ahora, implementa la solución elegante."
- Sáltate esto para fixes simples y obvios — no sobre-ingenierices.
- Desafía tu propio trabajo antes de presentarlo.

### 6. Corrección autónoma de bugs
- Ante un reporte de bug: simplemente arréglalo. No pidas que te lleven de la mano.
- Apunta a logs, errores, tests fallidos — y resuélvelos.
- Cero cambios de contexto requeridos del usuario.
- Arregla tests de CI fallidos sin que te digan cómo.

### Gestión de tareas
- **Planear primero:** escribe el plan en `tasks/todo.md` con items checkeables.
- **Verificar el plan:** valida con el usuario antes de empezar la implementación.
- **Rastrear progreso:** marca items como completos sobre la marcha.
- **Explicar cambios:** resumen de alto nivel en cada paso.
- **Documentar resultados:** agrega una sección de review a `tasks/todo.md`.
- **Capturar lecciones:** actualiza `tasks/lessons.md` después de correcciones.

El directorio `tasks/` existe desde 2026-07-01: `todo.md` contiene el plan maestro del refactor (con el inventario de slop auditado) y `lessons.md` las reglas aprendidas. Revisar ambos al inicio de cada sesión.

### Principios fundamentales
- **Simplicidad primero:** cada cambio tan simple como sea posible; impactar el mínimo de código.
- **Cero pereza:** encuentra causas raíz. Nada de fixes temporales. Estándar de desarrollador senior.
- **Impacto mínimo:** los cambios solo tocan lo necesario; evita introducir bugs.
- Y el que ya rige este repo: **cualquier cambio al proyecto debe reflejarse en este `CLAUDE.md`** (ver aviso al inicio).

## Tooling de Refactor: Subagentes y Skills (creado 2026-07-01)

Infraestructura para el refactor completo (mantener funcionalidad + UI temática MMA + borrar slop). El plan maestro con el inventario de slop auditado está en `tasks/todo.md`.

**Subagentes (`.claude/agents/`)** — workers con un solo trabajo cada uno:

| Agente | Rol | Herramientas |
|---|---|---|
| `slop-auditor` | Veredicto BORRABLE/NO BORRABLE con evidencia repo-wide antes de cualquier eliminación. Solo lee. | Read, Grep, Glob, Bash |
| `backend-refactorer` | Ejecuta cambios en api/, scripts/, tests/, requirements. Conoce los contratos frágiles (16 features, `probabilities[1]`, CSV en runtime, sys.path). | Todas de archivos + Bash |
| `mma-ui-builder` | Trabajo en frontend/ aplicando el design system Fight Night. Preserva IDs del DOM y contrato de API. | Todas de archivos + Bash |
| `stack-verifier` | Levanta el stack real, corre tests, compara contra baseline; reporta PASS/FAIL. Nunca modifica. | Read, Grep, Glob, Bash |

**Skills (`.claude/skills/`)** — procedimientos/conocimiento reutilizable:

| Skill | Contenido |
|---|---|
| `mma-run-stack` | Cómo levantar y verificar Redis + API + frontend + Ollama; troubleshooting |
| `slop-audit` | Estándar de evidencia (4 checks) para borrar código + trampas conocidas del repo |
| `mma-ui-theme` | Design system Fight Night: tokens de corners rojo/azul, oro de campeonato, tipografía, componentes (tale of the tape, fight meter, octágono), reglas de compatibilidad |
| `refactor-verify` | Definición de "terminado": baseline, pytest, paridad de /predict, smoke de frontend, docs |
| `sync-claude-md` | Procedimiento para mantener este archivo como fuente de verdad tras cada cambio |

Patrón de uso: las skills guardan el CÓMO (atemporal), `tasks/todo.md` guarda el QUÉ (inventario puntual), los agentes son QUIÉN ejecuta. Los agentes leen las skills relevantes al arrancar (está en sus prompts).

## Consideraciones

- **Uso responsable:** las predicciones son para análisis/entretenimiento; el modelo actual es dummy y NO debe usarse para apuestas.
- **Odds de apuestas:** nunca son input del modelo ML; solo comparación post-predicción para detectar value bets y validar contra el mercado.
- **Scraping:** mantener rate limiting (1–2s entre requests) y manejo de errores tolerante a cambios de HTML.
- Siempre que cambien los archivos, actualiza este `CLAUDE.md`.
