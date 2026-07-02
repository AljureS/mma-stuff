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

Es un proyecto en **fase de desarrollo/prototipo**. Lo que funciona de verdad y lo que no:

**Implementado y funcional:**
- API FastAPI completa (`api/main.py`) con cache Redis y validación Pydantic
- Cliente LLM con fallback OpenAI → Ollama, reintentos, circuit breakers (`api/llm_client.py`) + 15 tests unitarios
- Scraping automático de UFCStats cuando un peleador no existe en el CSV o sus datos tienen >7 días (`get_fighter_data` en `main.py` → `MMADataCollector.search_and_scrape_fighter`)
- Frontend HTML/JS/Tailwind que consume la API

**Placeholder / simulado (NO funcional en producción):**
- **El modelo ML actual es dummy**: `models/mma_prediction_model.pkl` fue generado por `scripts/setup_dev_data.py` entrenando XGBoost (`n_estimators=100`) sobre **datos aleatorios**. Las probabilidades que devuelve `/predict` no tienen valor predictivo real.
- `GET /events/upcoming`: eventos hardcodeados (UFC 300 ficticio)
- `GET /analytics/model-performance` y `GET /analytics/betting-roi`: números hardcodeados
- `POST /retrain`: el background task existe pero todo su cuerpo está comentado (no-op)
- `get_betting_insights()`: odds hardcodeadas (-120/+100), no llama a ninguna API real
- `get_recent_form()` y `get_current_ranking()`: retornan valores fijos de ejemplo
- **PostgreSQL no se usa**: existe `database_schema.sql` (tablas fighters/fights/predictions + seed data) y `psycopg2` en requirements, pero la API lee/escribe exclusivamente el CSV `data/fighters_complete.csv`
- `api/ml_system.py` (`MMAPredictor`): módulo de entrenamiento standalone con las 16 features "ideales"; **no es importado por `main.py`** y sus fuentes de datos están simuladas

**Bugs conocidos:**
- La cache key de Redis `prediction:{fighter_a}:{fighter_b}` no normaliza nombres ni orden: "A vs B" y "B vs A" generan entradas distintas
- `main.py` calcula solo 10 features reales y rellena con ceros hasta 16 (ver sección Features)

## Estructura Real del Proyecto

```
mma-stuff/
├── CLAUDE.md                      # Este archivo (fuente de verdad)
├── README.md                      # Readme general
├── ARCHITECTURE.md                # Notas de arquitectura
├── IMPLEMENTATION_SUMMARY.md      # Resumen de implementación LLM
├── README_LLM.md                  # Doc del sistema LLM
├── database_schema.sql            # Schema PostgreSQL (NO usado por la API)
├── test_scraping.py               # Script manual de prueba del scraper
├── api/
│   ├── main.py                    # Servidor FastAPI (toda la API + feature engineering)
│   ├── llm_client.py              # Cliente LLM con fallback OpenAI → Ollama
│   ├── ml_system.py               # MMAPredictor standalone (entrenamiento, NO usado por la API)
│   ├── requirements.txt           # Dependencias Python
│   └── .env                       # Variables de entorno (gitignored, NO commitear)
├── scripts/
│   ├── data_collection.py         # MMADataCollector (scraping UFCStats/Sherdog/Tapology)
│   ├── setup_dev_data.py          # Genera modelo dummy + CSV con 20 peleadores seed
│   └── deployment_setup.sh        # Setup de deployment (solo Linux)
├── data/
│   └── fighters_complete.csv      # Base de datos de peleadores (~37 filas, crece con scraping)
├── models/
│   └── mma_prediction_model.pkl   # Modelo XGBoost (actualmente dummy)
├── frontend/
│   ├── index.html                 # UI (Tailwind CDN, Chart.js CDN, Font Awesome CDN)
│   ├── index.js                   # Lógica del cliente (API_BASE_URL = http://localhost:8000)
│   └── styles.css                 # Estilos custom
└── tests/
    ├── __init__.py
    └── test_llm_client.py         # 15 tests del cliente LLM (pytest + pytest-asyncio)
```

No existen `data/fight_history.csv` ni `data/training_data.csv` (mencionados en versiones anteriores de esta doc).

## Componente 1: API Backend (`api/main.py`)

### Endpoints

| Endpoint | Estado | Descripción |
|---|---|---|
| `GET /` | Real | Health check: estado, modelo cargado, conteo de peleadores |
| `POST /predict` | Real (modelo dummy) | Predicción de pelea con cache, features y análisis LLM |
| `GET /fighter/{name}` | Parcial | Stats reales del CSV; `recent_form` y `ranking` son placeholders |
| `GET /search/fighters/{query}` | Real | Búsqueda fuzzy (`str.contains`, case-insensitive) sobre el CSV, `limit` default 10 |
| `GET /events/upcoming` | Placeholder | Eventos hardcodeados; sí ejecuta predicciones reales sobre ellos (sin LLM) |
| `POST /retrain` | No-op | Lanza background task cuyo cuerpo está completamente comentado |
| `GET /analytics/model-performance` | Placeholder | Métricas hardcodeadas |
| `GET /analytics/betting-roi` | Placeholder | ROI hardcodeado |
| `GET /health/llm` | Real | Estado de proveedores LLM y circuit breakers |

### Flujo de `/predict`

1. Verificar cache Redis (`prediction:{fighter_a}:{fighter_b}`, TTL 3600s). Hit → retorno inmediato.
2. `get_fighter_data()` para cada peleador (ver "Datos de peleadores" abajo). Si alguno no se encuentra ni se puede scrapear → 404 con nombres faltantes.
3. `engineer_fight_features()` genera el vector de 16 posiciones.
4. `prediction_model.predict_proba([features])` — **convención: `probabilities[1]` = probabilidad de que gane fighter_a**.
5. Si `include_llm_analysis=true` (default): análisis LLM en español (max_tokens=800, temperature=0.7, prompt limita a ~700 palabras).
6. `get_betting_insights()` (hardcodeado) — las odds NO son input del modelo, solo comparación post-predicción.
7. Respuesta `FightPredictionResponse` + cache en Redis por 1 hora.

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

`safe_get()` maneja None/NaN/no-convertibles con los defaults indicados. Las 16 features "completas" (con scores compuestos, forma reciente, calidad de oponentes, style matchup) solo existen en `ml_system.py`, que no está conectado a la API. Cerrar esa brecha es trabajo pendiente.

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

## Componente 3: Sistema de Entrenamiento (`api/ml_system.py`) — STANDALONE

Clase `MMAPredictor`. **No es usado por la API**; es el diseño objetivo del modelo y sirve para entrenar. Sus fuentes de datos (`_get_ufc_stats`, `_get_betting_odds`, `_get_social_sentiment`) retornan datos simulados, y su `main()` entrena con datos aleatorios.

**Las 16 features objetivo** (`feature_columns`): `height_diff`, `reach_diff`, `age_diff`, `experience_diff`, `win_rate_diff`, `finish_rate_diff`, `takedown_acc_diff`, `takedown_def_diff`, `sig_str_acc_diff`, `sig_str_def_diff`, `cardio_score_diff`, `power_score_diff`, `grappling_score_diff`, `recent_form_diff`, `opponent_quality_diff`, `style_matchup_score`.

**Hiperparámetros de `train_model()`:** XGBClassifier con `n_estimators=1000`, `learning_rate=0.01`, `max_depth=6`, `subsample=0.8`, `colsample_bytree=0.8`, split 80/20, early stopping 50 rounds, métricas accuracy/log loss + feature importance.

Las odds de apuestas y el sentiment social se recopilan en `load_fighter_data()` pero **no están en `feature_columns`** — no son input del modelo, solo contexto/comparación.

## Componente 4: Recolección de Datos (`scripts/data_collection.py`)

Clase `MMADataCollector` (requests + BeautifulSoup; selenium está en requirements e importado pero **sin uso real** en el código).

- `search_and_scrape_fighter(name)` — **el método que usa la API**. Busca en UFCStats por la inicial del apellido (`?char=X&page=all`), match fuzzy case-insensitive, parsea altura/peso/alcance/stance/récord, baja stats detalladas del perfil (striking/takedown accuracy/defense, historial de peleas), infiere `weight_class` por peso en libras. Defaults si faltan stats: striking_accuracy 50, striking_defense 55, takedown_accuracy 40, takedown_defense 70, age 30.
- `scrape_ufc_stats(max_fighters)` — scraping masivo de listados (páginas 1–49), rate limit 1s.
- `get_fighter_detailed_stats(profile_url)` — stats del perfil + fight history.
- `scrape_sherdog_rankings()` — top 15 por división.
- `scrape_tapology_events()` — eventos futuros.
- `get_betting_odds_historical()` — The Odds API, requiere API key (placeholder `YOUR_API_KEY`).
- `get_social_sentiment()` / Reddit / Twitter — placeholders con valores fijos.

Prueba manual del scraper: `python test_scraping.py` (busca a Mateusz Gamrot).

## Componente 5: Frontend (`frontend/`)

- `index.html`: UI con TailwindCSS (CDN), Chart.js (CDN), Font Awesome 6 (CDN). Referencia `styles.css` e `index.js` (rutas corregidas 2026-06-10).
- `index.js`: `API_BASE_URL = 'http://localhost:8000'`. Búsqueda de peleadores con debounce de 500ms, predicción vía `POST /predict` (siempre con `include_llm_analysis: true`), gráfico doughnut de probabilidades, factores clave, análisis LLM, betting insights, y carga de `/events/upcoming` al iniciar.
- `styles.css`: estilos custom mínimos.

## Datos

**`data/fighters_complete.csv`** — única fuente de datos de la API. Columnas:
`name, wins, losses, draws, height, reach, age, weight_class, ranking, striking_accuracy, striking_defense, takedown_accuracy, takedown_defense, last_updated, weight, stance, fight_history`

Las últimas 4 columnas las agrega el scraper. Alturas/alcances en cm, peso en lbs. Se siembra con 20 peleadores vía `setup_dev_data.py` y crece automáticamente con el auto-scraping (~37 filas actualmente). **La API escribe en este archivo en runtime** (por eso aparece modificado en git).

**`models/mma_prediction_model.pkl`** — XGBoost serializado con pickle. El actual es dummy (ver Estado Actual). Para regenerarlo: `python scripts/setup_dev_data.py` desde la raíz del proyecto.

**`database_schema.sql`** — schema PostgreSQL con seed data. No conectado a nada todavía.

**`dump.rdb`** — dump de Redis generado en runtime; no es código fuente (candidato a .gitignore).

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

Deployment Linux: `scripts/deployment_setup.sh` (verifica SO, permisos, espacio en disco; configura el stack completo).

## Tests

```bash
pytest tests/test_llm_client.py -v   # 15 tests: circuit breaker, fallback, reintentos, health check
python test_scraping.py              # prueba manual del scraper contra UFCStats (red real)
```

Los tests del LLM mockean OpenAI y aiohttp (pytest-asyncio + pytest-mock). No hay tests para `main.py` ni `ml_system.py`.

## Stack Tecnológico

- **Backend:** Python, FastAPI 0.104, uvicorn, Pydantic 2.5, pandas, numpy, XGBoost 1.7, scikit-learn, redis-py, aiohttp, requests + BeautifulSoup4, openai 2.41, python-dotenv
- **Frontend:** HTML/JS vanilla + TailwindCSS, Chart.js y Font Awesome por CDN
- **Infra activa:** Redis (cache). **Infra declarada pero no conectada:** PostgreSQL, Nginx, Docker, Supervisor
- **LLM:** OpenAI gpt-4o-mini (primario) + Ollama Qwen2.5:7b (fallback local)

## Trabajo Pendiente Prioritario

1. **Entrenar un modelo real**: el pkl actual es dummy. Requiere construir un dataset de peleas históricas (no existe `training_data.csv`) y conectar el pipeline de `ml_system.py` con datos reales.
2. **Cerrar la brecha de features**: `main.py` calcula 10 de 16 features; implementar los scores compuestos, forma reciente, calidad de oponentes y style matchup de `ml_system.py` en el flujo de la API.
3. Normalizar la cache key de Redis (orden y casing de nombres).
4. Conectar PostgreSQL o eliminar la dependencia declarada.
5. Implementar de verdad `/retrain`, betting insights, recent form y rankings.

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

El directorio `tasks/` no existe aún; créalo (con `todo.md` y `lessons.md`) la primera vez que se necesite.

### Principios fundamentales
- **Simplicidad primero:** cada cambio tan simple como sea posible; impactar el mínimo de código.
- **Cero pereza:** encuentra causas raíz. Nada de fixes temporales. Estándar de desarrollador senior.
- **Impacto mínimo:** los cambios solo tocan lo necesario; evita introducir bugs.
- Y el que ya rige este repo: **cualquier cambio al proyecto debe reflejarse en este `CLAUDE.md`** (ver aviso al inicio).

## Consideraciones

- **Uso responsable:** las predicciones son para análisis/entretenimiento; el modelo actual es dummy y NO debe usarse para apuestas.
- **Odds de apuestas:** nunca son input del modelo ML; solo comparación post-predicción para detectar value bets y validar contra el mercado.
- **Scraping:** mantener rate limiting (1–2s entre requests) y manejo de errores tolerante a cambios de HTML.
- Siempre que cambien los archivos, actualiza este `CLAUDE.md`.
