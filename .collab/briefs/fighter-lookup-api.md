# Brief (HalJordan): API no bloqueante para la búsqueda/carga de peleadores + robustez

Objective: que un `/predict` que scrapea (1–10 s por peleador) NO congele el event loop (las búsquedas `/search/fighters/` deben seguir respondiendo en milisegundos mientras tanto), que dos scrapes concurrentes no corrompan el CSV, y que la búsqueda no devuelva 500 con caracteres especiales ni con Redis caído.

## Diagnóstico (verificado en vivo por Muad'Dib; no re-investigar)
- `predict_fight` y `get_fighter_stats` son `async def` pero llaman `get_fighter_data()` → `requests` síncrono (timeouts de 15 s + 10 s por peleador, ahora + 1 s de rate limit): bloquea TODO el servidor. Medido: `/search` tarda 0.30 s en vez de 0.002 s mientras corre un predict cuyo scrape falla rápido; con el scraper ya arreglado (`scripts/data_collection.py`) serán varios segundos.
- `GET /search/fighters/(` → 500: `str.contains(query)` trata el query como regex (igual en `_search_in_database`).
- Redis caído → `/predict` devuelve 500 (la excepción de conexión cae en el `except Exception` genérico).
- `_update_or_add_to_csv` hace read-modify-write del CSV sin lock ni escritura atómica; al mover el scraping a threads, dos predicts concurrentes podrían perder filas.

## Cambios exactos (`api/main.py`)
1. Imports: `import asyncio`, `import threading`, `from starlette.concurrency import run_in_threadpool` (starlette viene con FastAPI; sin dependencias nuevas).
2. `predict_fight`: reemplazar las dos llamadas secuenciales a `get_fighter_data` por
   `fighter_a_data, fighter_b_data = await asyncio.gather(run_in_threadpool(get_fighter_data, request.fighter_a), run_in_threadpool(get_fighter_data, request.fighter_b))`. Mantener los logs "Searching for fighter_a/b".
3. `get_fighter_stats`: `fighter_data = await run_in_threadpool(get_fighter_data, fighter_name)`; en la respuesta usar `name=fighter_data['name']` (nombre canónico del CSV, no el texto tecleado). El frontend va a llamar a este endpoint como "Buscar en UFCStats" cuando la búsqueda local no encuentra nada.
4. Lock: `_csv_lock = threading.Lock()` a nivel de módulo; en `get_fighter_data`, envolver `_update_or_add_to_csv(fresh_data)` + `_reload_fighter_database()` en `with _csv_lock:`. Dentro de `_update_or_add_to_csv`: al agregar una fila nueva, quedarse solo con las claves que son columnas del CSV (`{k: v for k, v in fighter_data.items() if k in df.columns}`), y escribir de forma atómica: `tmp = csv_path.with_name(csv_path.name + '.tmp'); df.to_csv(tmp, index=False); os.replace(tmp, csv_path)`.
5. Búsqueda: en `search_fighters` y en `_search_in_database` usar `str.contains(q, case=False, na=False, regex=False)` con `q = query.strip()`; en `_search_in_database` agregar un paso de match exacto case-insensitive (`fighter_database['name'].str.strip().str.lower() == q.lower()`) entre el exacto y el fuzzy. Si el query queda vacío tras strip, `/search` devuelve `results: []`, `count: 0`.
6. Cache tolerante a fallos: `redis.Redis.from_url(..., decode_responses=True, socket_connect_timeout=2, socket_timeout=2)`; envolver `redis_client.get(...)` y `redis_client.setex(...)` en `try/except redis.RedisError` → `logger.warning(...)` y seguir sin cache (`/predict` debe responder 200 igual con Redis caído). El health check `GET /` NO cambia.
7. NO tocar: el vector de 16 features (`engineer_fight_features`), `probabilities[1]` = fighter_a, `_normalize_cache_key`, `_swap_cached_prediction`, el prompt LLM, los modelos Pydantic, el mount de `/ui`, CORS, el bloque `__main__`, `_sanitize_csv_record`/`_nan_to_none`.

## Archivos que te pertenecen (no edites nada más)
`api/main.py`

## Contexto a leer primero
`AGENTS.md` ("Componente 1", "Flujo de /predict", "Datos de peleadores con auto-scraping"), `api/main.py` completo, `scripts/data_collection.py` (ya arreglado por vos en la tarea anterior: `search_and_scrape_fighter` ahora resuelve el challenge y tarda 1–10 s reales).

## No hacer
No tocar `scripts/`, `frontend/`, `tests/`, `data/`, `models/`, docs, `tasks/`, `.env*`, `requirements.txt`. No leer `api/.env`. No commitear. No borrar archivos. No hacer requests a internet.

## Tests (verde = todo pasa)
- `venv/bin/python -m pytest tests/ -q` → todos passed (llm_client + data_collection)
- `venv/bin/python -c "import ast; ast.parse(open('api/main.py').read())"` → sin error
- `cd api && ../venv/bin/python -c "import main"` → sin error (Redis puede no estar: `from_url` no conecta hasta el primer comando)
- Si tu sandbox lo permite (si no, reportalo como skipped): `cd api && ../venv/bin/uvicorn main:app --port 8010 &` y `curl -s 'http://127.0.0.1:8010/search/fighters/%28'` → 200 con `"results":[]`; luego matar el uvicorn.

## Reporte
Archivos cambiados, comandos corridos con resultado y el `git status` contra el que corrieron, lo que saltaste y por qué, preguntas abiertas. Última línea exacta: `DONE` o `BLOCKED: <motivo>`.
