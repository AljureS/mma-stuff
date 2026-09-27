> **Copia para Codex (HalJordan) de `CLAUDE.md`, la fuente única de verdad del proyecto.** NO editar este archivo a mano: tras cualquier cambio en `CLAUDE.md`, regenerarlo con `{ head -1 AGENTS.md; echo; cat CLAUDE.md; } > AGENTS.md` (regenerado 2026-09-26 tras el fix de búsqueda/carga de peleadores).

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
- API FastAPI (`api/main.py`, 635 LOC) con cache Redis (key normalizada, best-effort) y validación Pydantic — 5 endpoints reales + frontend estático en `/ui`. **Fix de concurrencia 2026-09-26:** el scraping (`requests` síncrono) corre en el threadpool de Starlette y para ambos peleadores en paralelo; antes se ejecutaba dentro de los handlers `async def` y congelaba TODO el servidor (la búsqueda del otro corner incluida) mientras duraba.
- Cliente LLM con fallback OpenAI → Ollama, reintentos, circuit breakers (`api/llm_client.py`) + 15 tests unitarios
- Scraping automático de UFCStats cuando un peleador no existe en el CSV o sus datos tienen >7 días (`get_fighter_data` en `main.py` → `MMADataCollector.search_and_scrape_fighter`). **Arreglado 2026-09-26:** el collector resuelve el challenge JS anti-bot de UFCStats (proof-of-work sha256 + `POST /__c`, cookie `_fmc`), busca por apellido ignorando sufijos (Jr./Sr./III), prefiere el match exacto y parsea stats REALES del perfil (Str. Acc./Def., TD Acc./Def., edad desde DOB). Antes devolvía 0 filas y el parser de perfil nunca funcionó (todos los peleadores tenían stats default).
- Frontend HTML/JS/Tailwind que consume la API (rediseño Fight Night 2026-07; autocompletado por corner + fallback "Buscar en UFCStats" + errores inline 2026-09-26)

**Placeholder / simulado (lo que queda):**
- **El modelo ML actual es dummy**: `models/mma_prediction_model.pkl` fue generado por `scripts/setup_dev_data.py` entrenando XGBoost (`n_estimators=100`) sobre **datos aleatorios**. Las probabilidades que devuelve `/predict` no tienen valor predictivo real.
- `main.py` calcula solo 10 features reales y rellena con ceros hasta 16 (ver sección Features). **El padding NO es borrable**: el pkl espera exactamente 16 inputs.

**Issues conocidos:**
- Los 37 peleadores sembrados antes del 2026-09-26 tienen stats default (50/55/40/70, edad 30) en el CSV: se reemplazan por stats reales la primera vez que se piden (están stale >7 días → re-scrape automático).
- Uvicorn (`0.0.0.0:8000`) sigue hardcodeado en `python main.py` (no lee `API_HOST`/`API_PORT`). Redis ya lee `REDIS_URL` (2026-09-26).

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
├── Dockerfile                     # Imagen de la API (python:3.11-slim + libgomp1), deploy homelab 2026-09
├── compose.yaml                   # api (127.0.0.1:8000) + redis interno; data rw / models ro montados
├── .dockerignore                  # Excluye .env, data/, models/, venv/, tasks/, .claude/, .collab/
├── .collab/                       # Briefs y registros de delegación Muad'Dib → HalJordan (Codex)
├── README_LLM.md                  # Doc del sistema LLM
├── test_scraping.py               # Script manual de prueba del scraper
├── api/
│   ├── main.py                    # Servidor FastAPI (toda la API + feature engineering, 635 LOC)
│   ├── llm_client.py              # Cliente LLM con fallback OpenAI → Ollama
│   ├── requirements.txt           # 16 dependencias Python (podado 2026-07-01)
│   └── .env                       # Variables de entorno (gitignored, NO commitear)
├── scripts/
│   ├── data_collection.py         # MMADataCollector (scraping UFCStats + solver del challenge JS, 289 LOC)
│   └── setup_dev_data.py          # Genera modelo dummy + CSV con 20 peleadores seed
├── data/
│   └── fighters_complete.csv      # Base de datos de peleadores (~41 filas al 2026-09-26, crece con scraping)
├── models/
│   └── mma_prediction_model.pkl   # Modelo XGBoost (actualmente dummy)
├── frontend/
│   ├── index.html                 # UI Fight Night (Tailwind CDN, Chart.js CDN, Font Awesome CDN)
│   ├── index.js                   # Lógica del cliente, 534 LOC (autocompletado por corner, lookup UFCStats, predict)
│   └── styles.css                 # Estilos custom del tema
└── tests/
    ├── __init__.py
    ├── test_llm_client.py         # 15 tests del cliente LLM (pytest + pytest-asyncio)
    ├── test_data_collection.py    # 22 tests del scraper, offline con fixtures (2026-09-26)
    ├── test_main_search.py        # 6 tests de _search_in_database (main.py) sin servidor ni Redis
    ├── test_main_csv.py           # 3 tests de _update_or_add_to_csv/_reload sobre un CSV temporal (CSV_PATH)
    └── fixtures/                  # HTML real de UFCStats: challenge, lista "R" recortada, perfil Rosas Jr.
```

Borrados en el refactor 2026-07-01: `ARCHITECTURE.md`, `IMPLEMENTATION_SUMMARY.md`, `database_schema.sql`, `api/ml_system.py`, `scripts/deployment_setup.sh`, `dump.rdb`. No existen `data/fight_history.csv` ni `data/training_data.csv` (mencionados en versiones antiguas de esta doc).

## Componente 1: API Backend (`api/main.py`)

### Endpoints

| Endpoint | Estado | Descripción |
|---|---|---|
| `GET /` | Real | Health check: estado, modelo cargado, conteo de peleadores |
| `POST /predict` | Real (modelo dummy) | Predicción de pelea con cache, features y análisis LLM |
| `GET /fighter/{name}` | Real | Stats del CSV (NaN→None); `ranking` sale de la columna `ranking` del CSV (null si falta); ya no existe `recent_form`. Dispara auto-scraping si el peleador falta o está stale (en threadpool). Desde 2026-09-26 `name` devuelve el nombre canónico del CSV, no el texto tecleado; es el endpoint que usa el botón "Buscar en UFCStats" del frontend |
| `GET /search/fighters/{query}` | Real | Búsqueda fuzzy (`str.contains`, case-insensitive, `regex=False`) sobre el CSV en memoria (NO scrapea), `limit` default 10. Fix 2026-07-01: sanitiza NaN (antes devolvía 500). Fix 2026-09-26: query literal + `strip()` (antes `(` → 500 por regex inválido); query vacío → `results: []` |
| `GET /health/llm` | Real | Estado de proveedores LLM y circuit breakers |
| `GET /ui/` | Real (estático) | Sirve `frontend/` con `StaticFiles` (mismo origen que la API; se monta solo si existe el directorio). Añadido 2026-09-26 para el deploy detrás de `tailscale serve` |

Eliminados 2026-07-01 (devuelven 404): `POST /retrain`, `GET /events/upcoming`, `GET /analytics/model-performance`, `GET /analytics/betting-roi`.

### Flujo de `/predict`

1. Verificar cache Redis con **key normalizada** `prediction:{min}:{max}` (nombres `strip().lower()` ordenados; TTL 3600s). Hit → si el orden de peleadores del request difiere del cacheado, `_swap_cached_prediction()` intercambia nombres/probabilidades y **niega los `key_factors`** (son diferencias a−b) antes de responder. La llamada a Redis va en el threadpool; si falla (`redis.RedisError`) → warning y se sigue sin cache (antes: 500).
2. `get_fighter_data()` para AMBOS peleadores en paralelo: `await asyncio.gather(run_in_threadpool(get_fighter_data, a), run_in_threadpool(get_fighter_data, b))` (ver "Datos de peleadores" abajo). Si alguno no se encuentra ni se puede scrapear → 404 con nombres faltantes.
3. `engineer_fight_features()` genera el vector de 16 posiciones.
4. `prediction_model.predict_proba([features])` — **convención: `probabilities[1]` = probabilidad de que gane fighter_a**.
5. Si `include_llm_analysis=true` (default): análisis LLM en español (max_tokens=800, temperature=0.7, prompt limita a ~700 palabras).
6. Respuesta `FightPredictionResponse` (sin `betting_insights` desde 2026-07-01) + cache en Redis por 1 hora (best-effort: si `setex` falla, solo warning).

Helpers de sanitización: `_nan_to_none()` y `_sanitize_csv_record()` (main.py) — aplicar a TODA respuesta construida desde filas del CSV (tiene NaN).

### Datos de peleadores con auto-scraping (`get_fighter_data`)

- Corre SIEMPRE en un thread del pool (`run_in_threadpool`), nunca directamente en el event loop: usa `requests` síncrono y puede tardar 2–25 s.
- Busca en el CSV en memoria (query `strip()`eado): primero match exacto por `name`, luego exacto case-insensitive, luego fuzzy (`str.contains(..., regex=False)`) SOLO si el substring identifica a un único peleador — "Silva" con Natalia Silva y Jean Silva en el CSV → `None` (→ intento de scraping → 404 y la UI pide el nombre completo). Antes tomaba la primera fila en silencio (fix ronda 2 de review, 2026-09-26). Tras un scrape exitoso, la relectura usa el nombre canónico devuelto por UFCStats (`fresh_data['name']`), no el texto tecleado.
- Si el peleador existe y `last_updated` tiene **menos de 7 días** → usa el dato cacheado.
- Si no existe o está stale → scrapea UFCStats vía `MMADataCollector.search_and_scrape_fighter()` y, bajo `_csv_lock` (`threading.Lock`, dos scrapes concurrentes no se pisan), actualiza/agrega la fila al CSV con `last_updated` (ISO) — filas nuevas limitadas a las columnas existentes, listas/dicts (`fight_history`) serializados con `str()` al actualizar una fila existente (antes `df.loc[...] = lista` lanzaba "Must have equal len keys and value" y el peleador stale NUNCA se refrescaba: bug detectado y corregido 2026-09-26), escritura atómica (`fighters_complete.csv.tmp` + `os.replace`) — y recarga `fighter_database` en memoria. La ruta vive en la constante `CSV_PATH` (`main.py`), usada por startup, escritura y recarga.
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

- Redis: `redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)` con default `redis://localhost:6379/0` (desde 2026-09-26). En Docker, `compose.yaml` lo pisa con `redis://redis:6379/0`. Las llamadas `get`/`setex` de `/predict` corren en el threadpool (`await run_in_threadpool(...)`, para que un Redis que acepta la conexión pero no responde no congele el loop hasta 2 s) y están envueltas en `try/except redis.RedisError`: con Redis caído la API responde 200 sin cache (verificado 2026-09-26 con `REDIS_URL` apuntando a un puerto cerrado). `GET /` no depende de Redis.
- Uvicorn: **hardcodeado** `0.0.0.0:8000` en `python main.py` (las variables `API_HOST`/`API_PORT` no se leen). Reload activo si se pasa `--reload` o existe env `DEBUG`. En Docker el `CMD` llama a `uvicorn main:app --app-dir /app/api` directo (sin reload aunque el .env tenga `DEBUG=true`).
- CORS: `allow_origins` desde `CORS_ORIGINS` (lista por comas, default `http://localhost:3000,http://127.0.0.1:3000`) — restringido 2026-09-26 (antes `*`: cualquier web abierta podía gastar la key de OpenAI vía `/predict`). Servido desde `/ui/` es mismo origen y no necesita CORS; abrir `index.html` con `file://` ya no funciona (usar :3000).
- Startup: carga `models/mma_prediction_model.pkl` y `data/fighters_complete.csv` (constante `CSV_PATH`) con rutas relativas a la raíz del proyecto (`Path(__file__).parent.parent`).
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

Clase `MMADataCollector` (requests + BeautifulSoup, 289 LOC; reescrita 2026-09-26 para volver a funcionar). Cadena de producción:

- `search_and_scrape_fighter(name)` — **el método que usa la API** (vía `get_fighter_data` en main.py, importado con hack de `sys.path`). Elige la letra con `_search_letter(name)`: última palabra del nombre ignorando sufijos `Jr./Sr./II/III/IV` ("Raul Rosas Jr." → `R`), pide `?char=X&page=all` vía `_get`, recorre TODAS las filas de datos (≥10 `td`) y prefiere el match **exacto** normalizado (lower, sin puntos, guiones → espacio); sin exacto, acepta un match por substring SOLO si es único (con 2+ candidatos — p. ej. "Rosas" → Jessie Rosas y Raul Rosas Jr., o "Rodriguez" — loguea warning y devuelve `None`; la UI pide el nombre completo). Parsea altura/peso/alcance/stance/récord de la fila y llama a `get_fighter_detailed_stats`. Infiere `weight_class` por peso en libras. Defaults si faltan stats: striking_accuracy 50, striking_defense 55, takedown_accuracy 40, takedown_defense 70, age 30. Devuelve `None` si no encuentra y nunca lanza.
- `_throttle()` — rate limit GLOBAL del módulo (lock + `time.monotonic()`): garantiza ≥ `request_delay` (1.0 s; los tests lo ponen en 0) entre requests consecutivos a UFCStats, incluyendo el GET → POST `/__c` → GET del challenge y los scrapes paralelos que la API lanza en threads distintos (comparten `_last_request_at`).
- `_get(url, timeout)` — TODOS los GET pasan por aquí (cada uno y el POST del challenge llaman antes a `_throttle()`). UFCStats sirve desde ~2026-07 un interstitial anti-bot ("Checking your browser…", 3 KB) con un proof-of-work en JS: hallar `n` tal que `sha256(f"{nonce}:{n}")` en hex empiece con N ceros (hoy N=2, ~150 iteraciones) y hacer `POST /__c` con `nonce` y `n`; el servidor responde 204 y setea la cookie `_fmc` en la `requests.Session`, tras lo cual el mismo GET devuelve la página real. `_get` detecta el challenge por `var nonce="..."`, lo resuelve (tope 2M iteraciones) y repite el GET UNA sola vez; queda resuelto para toda la sesión. Esto es lo que hacía que el scraper "devolviera 0 filas" desde julio.
- `get_fighter_detailed_stats(profile_url)` — stats del perfil + fight history. **Es producción, NO borrar**. Parser corregido 2026-09-26: en los `li.b-list__box-list-item` el título está en `<i class="b-list__box-item-title">` y el valor es el texto restante del `li` (nunca existió `b-list__box-item-value`, por eso todos los peleadores del CSV quedaron con stats default). Devuelve SOLO `striking_accuracy`, `striking_defense`, `takedown_accuracy`, `takedown_defense` (float sin `%`; un valor `--`, o las CUATRO métricas presentes y en `0%` — así muestra UFCStats a un peleador sin peleas UFC registradas, p. ej. los finalistas de TUF — se OMITEN para que apliquen los defaults, nunca se guardan como 0.0; un `0%` legítimo acompañado de otras métricas (o de `--`) sí se guarda), `age` (años cumplidos desde `DOB:`; omitido si `--`) y `fight_history` — nada más, porque `main.py` concatena filas nuevas al CSV con todas las claves.
- Parsers: `_parse_height`, `_parse_weight`, `_parse_reach`, `_infer_weight_class`, `_normalize_stat_name` (acepta `Str. Def` sin punto final), `_parse_stat_value`, `_normalized_name`.
- Logging con `logging.getLogger(__name__)`; ya no hay `print`.

Eliminados 2026-07-01 (solo eran alcanzables desde un `main()` que nunca corría, o desde nadie): `scrape_ufc_stats`, `scrape_sherdog_rankings`, `scrape_tapology_events`, `get_betting_odds_historical`, `get_social_sentiment` + helpers Reddit/Twitter, `save_data`, `main()`, imports de selenium/pandas/time/json.

Tests offline: `tests/test_data_collection.py` (22 tests) con una `FakeSession` y las fixtures reales de `tests/fixtures/` (`ufcstats_challenge.html` con nonce `5ced8977889ef36c`, `ufcstats_fighters_R.html` recortada a 5 peleadores, `ufcstats_fighter_rosas_jr.html`). Cubren: challenge resuelto una vez con POST correcto, parser de lista (Rosas Jr. 12-1-0, 175.26 cm, 170.18 cm), parser de perfil (42/52/54/25 + edad), sufijos, exacto-antes-que-substring, substring único aceptado / ambiguo → `None`, stats `--`/todas-en-`0%` omitidas y defaults aplicados (un solo `0%` se conserva), not found sin GET de perfil y rate limit (lista→perfil y el round-trip del challenge).

Prueba manual del scraper (red real): `python test_scraping.py` (busca a Mateusz Gamrot). Verificado en vivo 2026-09-26: Raul Rosas Jr. 12-1-0 en 2.3 s, Raoni Barcelos 22-5-0, "Topuria" → Ilia Topuria; nombre inexistente → `None` en 0.4 s. Si UFCStats endurece el challenge o cambia `/__c`, `_get` devuelve el interstitial tal cual (0 filas) y la API degrada a datos del CSV.

**Las 16 features objetivo del modelo real** (heredadas del borrado `ml_system.py`, para cuando se entrene en serio): `height_diff`, `reach_diff`, `age_diff`, `experience_diff`, `win_rate_diff`, `finish_rate_diff`, `takedown_acc_diff`, `takedown_def_diff`, `sig_str_acc_diff`, `sig_str_def_diff`, `cardio_score_diff`, `power_score_diff`, `grappling_score_diff`, `recent_form_diff`, `opponent_quality_diff`, `style_matchup_score`. Hiperparámetros de referencia: XGBClassifier `n_estimators=1000`, `learning_rate=0.01`, `max_depth=6`, `subsample=0.8`, `colsample_bytree=0.8`, split 80/20, early stopping 50.

## Componente 4: Frontend (`frontend/`)

UI rediseñada 2026-07-01 con el design system **Fight Night** (ver skill `mma-ui-theme`: tokens arena/corner/gold/canvas, Barlow Condensed + Inter por Google Fonts, corners rojo/azul, oro solo para title fight).

- `index.html` (288 LOC): header cartelera, matchup con corner rojo | VS | corner azul, opciones (peso/evento/checkbox title fight con badge dorado), `resultsSection` (banner de ganador con glow de corner, chart, key factors, análisis de esquina), `loadingModal` con octágono girando. Config de Tailwind inline con los tokens. **El bloque JS inline duplicado fue eliminado** — `index.js` es la única fuente. Añadido 2026-09-26: cada input de peleador (`autocomplete="off"`, `role="combobox"`) tiene debajo una `<ul id="fighter{A,B}Suggestions" class="suggestions suggestions-{red,blue}">` y un bloque `#fighter{A,B}Lookup` (texto `.lookup-message` + botón `.lookup-btn[data-input]` "Buscar en UFCStats"); sobre el botón de predecir hay un `#errorBanner` con `#errorMessage` que reemplaza a los `alert()`.
- `index.js` (534 LOC): `API_BASE_URL` = `window.location.origin`, salvo `file:` o puerto 3000 (dev local) → `'http://localhost:8000'`. Consume `GET /search/fighters/{q}?limit=8` (debounce 300 ms), `GET /fighter/{name}` (fallback "Buscar en UFCStats": dispara el scraping en el backend y rellena el input con el nombre canónico `stats.name`) y `POST /predict` (siempre `include_llm_analysis: true`). **Búsqueda por corner (fix 2026-09-26):** `searchState[fighterA|fighterB]` guarda timer de debounce, número de secuencia y sugerencias por input — antes un único timer compartido hacía que escribir en el corner azul cancelara la búsqueda del rojo, una respuesta lenta podía pisar a una más nueva, y con 0 resultados el récord anterior quedaba visible (el peleador "aparecía" pero era otro → 404 al predecir). Ahora cada tecla incrementa `seq` (invalida al instante búsquedas y lookups en vuelo, revalidado tras cada `await`), con 0 resultados o error se vacían sugerencias y récord (y el error se avisa inline), la lista de sugerencias es clickeable (mousedown con `preventDefault` para no perder el foco) y navegable con ↑/↓/Enter/Esc, el récord se muestra solo si el match es exacto o único, y con 0 resultados se ocultan récord y lista y aparece el fallback. Doughnut con colores de corner, key factors con iconos y color según a quién favorecen (signo del diff, ver skill), banner de ganador (`winnerBanner`/`titleBeltNote` — title fight se toma del request). Patrón destroy-antes-de-recrear del chart. Errores → `showError()` inline; el 404 de `/predict` se traduce a español con el nombre faltante. Los key factors se construyen con `createElement`/`textContent` (sin `innerHTML`: los nombres vienen del input del usuario).
- `styles.css` (334 LOC): componentes custom del tema — spinner octágono (clip-path + conic-gradient), glows de ganador por corner/oro, clases dinámicas que el JS aplica (`.winner-*`, `.factor-*`, y desde 2026-09-26 `.suggestions`/`.suggestion-item`/`.is-active`, `.lookup-row`/`.lookup-btn`/`.is-loading|.is-notfound|.is-error`, `.error-banner`; van aquí y no como utilidades Tailwind por el CDN).

Los IDs del DOM son contrato con `index.js` — la lista completa vive en la skill `mma-ui-theme` (reglas de compatibilidad).

## Datos

**`data/fighters_complete.csv`** — única fuente de datos de la API. Columnas:
`name, wins, losses, draws, height, reach, age, weight_class, ranking, striking_accuracy, striking_defense, takedown_accuracy, takedown_defense, last_updated, weight, stance, fight_history`

Las últimas 4 columnas las agrega el scraper. Alturas/alcances en cm, peso en lbs. Se siembra con 20 peleadores vía `setup_dev_data.py` y crece automáticamente con el auto-scraping (~41 filas al 2026-09-26). **La API escribe en este archivo en runtime** (por eso aparece modificado en git). Los 37 peleadores previos al 2026-09-26 tienen stats default (50/55/40/70, edad 30) porque el parser de perfil nunca funcionó; al estar stale se re-scrapean con stats reales la primera vez que participan en un `/predict` o `/fighter/{name}`.

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
REDIS_URL=redis://localhost:6379             # Leída desde 2026-09-26 (default redis://localhost:6379/0)
CORS_ORIGINS=                                 # Opcional; default http://localhost:3000,http://127.0.0.1:3000
```

Presentes en `.env` pero **no leídas por el código** (reservadas para producción): `DATABASE_URL`, `API_HOST`, `API_PORT`, `SECRET_KEY`, `LOG_LEVEL`, `ENVIRONMENT`. No existe `.env.example` (está gitignored); para reproducir el .env usa la lista de arriba.

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

## Deploy en el Home Lab (Tailscale, 2026-09-26)

Copia (no movimiento) del proyecto al homelab (`simon@homelab`, Debian 13, 6 GB RAM) accesible SOLO dentro del tailnet. Plan, checklist con evidencia y verificador en `tasks/todo.md` y `tasks/deploy/`.

```
MacBook ──HTTPS (tailnet)──> tailscale serve (homelab:443) ──> 127.0.0.1:8000 api (docker)
                                                               ├─ /     health
                                                               ├─ /ui/  frontend
                                                               └─ redis (red interna, sin puerto publicado)
```

- Ubicación en el server: `~/apps/mma-stuff/` (sin venv/.git; `api/.env` copiado aparte con `chmod 600`).
- Levantar/actualizar: `rsync` desde la Mac (sin `--delete`) + `docker compose up -d --build` en el server. Sin Ollama (qwen2.5:7b no cabe): LLM solo OpenAI.
- Exposición: `tailscale serve --bg 8000` (NUNCA `funnel`, nunca puertos en `0.0.0.0`). URL: `https://homelab.<tailnet>.ts.net/ui/`.
- Quién entra: policy del tailnet en `tasks/deploy/tailnet-policy.hujson` (grant por device: solo el MacBook → homelab tcp:443/22). Agregar un device = sumarlo a `hosts` y al `src` del grant.
- Prerrequisitos del server (sudo, los corre el owner): `tasks/deploy/mma_prereqs.sh` (Docker oficial, rsync, grupo docker, `tailscale set --operator=simon`, tapa sin suspender).
- Healthchecks: redis con `redis-cli ping`; api sana solo si `models_loaded`, `fighters_count>0` y Redis responde (`depends_on: service_healthy`).
- **Incidente 2026-09-26:** `api/.env` estaba trackeado en git y pusheado a `origin/main` (repo público). Se des-trackeó (`git rm --cached`, el archivo sigue en disco). Las credenciales de ese archivo deben rotarse; purgar el historial remoto es decisión del owner.
- Verificador del plan: `tasks/deploy/verify_plan.sh` (lo corre un /loop durante la ejecución): Mac intacta vs manifest, diff en scope, nada en 0.0.0.0 en el server, funnel apagado, items marcados solo con evidencia en `tasks/deploy/evidence/`.

## Tests

```bash
pytest tests/ -v                     # 46 tests: 15 del cliente LLM + 22 del scraper (offline, con fixtures) + 9 de main.py (búsqueda local y escritura del CSV)
python test_scraping.py              # prueba manual del scraper contra UFCStats (red real)
```

Los tests del LLM mockean OpenAI y aiohttp (pytest-asyncio + pytest-mock); los del scraper inyectan una `FakeSession` con HTML real guardado en `tests/fixtures/`; `test_main_search.py` y `test_main_csv.py` importan `main` (sin levantar uvicorn ni conectar a Redis) y monkeypatchean `fighter_database` / `CSV_PATH` para probar `_search_in_database`, `_update_or_add_to_csv` y `_reload_fighter_database` sobre un CSV temporal. El resto de `main.py` (endpoints, threadpool, cache) solo se verifica por ejecución real (ver skill `refactor-verify`).

## Stack Tecnológico

- **Backend:** Python, FastAPI 0.104, uvicorn, Pydantic 2.5, pandas, numpy, XGBoost 1.7, scikit-learn (requerida para deserializar el pkl), redis-py, aiohttp, requests + BeautifulSoup4, openai 2.41, python-dotenv — 16 deps totales (podadas de 24 el 2026-07-01)
- **Frontend:** HTML/JS vanilla + TailwindCSS, Chart.js y Font Awesome por CDN
- **Infra activa:** Redis (cache). Toda la infra declarada-pero-no-conectada (PostgreSQL, Nginx, Docker, Supervisor) se eliminó en el refactor 2026-07-01.
- **LLM:** OpenAI gpt-4o-mini (primario) + Ollama Qwen2.5:7b (fallback local)

## Trabajo Pendiente Prioritario

1. **Entrenar un modelo real**: el pkl actual es dummy. Requiere construir un dataset de peleas históricas (no existe `training_data.csv`). Las 16 features objetivo e hiperparámetros de referencia están documentados al final de "Componente 3".
2. **Cerrar la brecha de features**: `main.py` calcula 10 de 16 features; implementar los scores compuestos, forma reciente, calidad de oponentes y style matchup en el flujo de la API (junto con el punto 1).
3. Parametrizar uvicorn por variables de entorno en `python main.py` (hoy hardcodeado; Redis ya lee `REDIS_URL`).

Resuelto 2026-09-26 (plan y evidencia en `tasks/todo.md`): scraper de UFCStats (challenge JS + parser de perfil + apellidos con sufijo), bloqueo del event loop por scraping síncrono dentro de `async def` (ahora threadpool + lock del CSV), `/search` con caracteres regex (500) y Redis caído (500), y búsqueda/carga de peleadores en la UI.

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
- **Scraping:** mantener rate limiting (`_throttle()`: ≥ 1 s entre requests consecutivos, global entre threads), scraping solo bajo demanda con cache de 7 días, y manejo de errores tolerante a cambios de HTML. UFCStats exige resolver un challenge JS (proof-of-work) que `_get` resuelve como lo haría un navegador; es uso personal de bajo volumen — no convertirlo en crawler masivo.
- Siempre que cambien los archivos, actualiza este `CLAUDE.md`.
