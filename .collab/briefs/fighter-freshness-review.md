# Brief (HalJordan): REVIEW independiente — frescura de datos de peleadores (solo lectura)

Sos el revisor del gate de consenso. NO edites ningún archivo. Leé el diff, reproducí lo que puedas y devolvé hallazgos con severidad y evidencia (archivo:línea), no órdenes. Un review limpio debe significar que el diff está limpio de verdad.

## Alcance (solo estos archivos; el resto del `git status` es de OTRA tarea en curso — modelo LLM Luna — y NO se revisa)
Diff a revisar: `git diff -- api/main.py scripts/data_collection.py tests/test_data_collection.py tests/test_main_csv.py frontend/index.html frontend/index.js frontend/styles.css` + archivo nuevo `tests/test_main_freshness.py` + las secciones de `CLAUDE.md` que hablan de frescura/`next_fight_date`/`refresh`/`force_refresh`/cache versionada (`git diff CLAUDE.md`, ignorando los hunks sobre gpt-6-luna/costos/README).
Fuera de alcance (no comentar): `api/llm_client.py`, `tests/test_llm_client.py`, `README.md`, `README_LLM.md`, `data/fighters_complete.csv`, `AGENTS.md` (copia generada de CLAUDE.md), `tasks/`, `.collab/`.

## Qué se cambió y por qué (contexto, no re-investigar)
UFCStats muestra hoy a Raul Rosas Jr. 12-1-0 con la pelea de esta noche como `next`; la app congelaba el récord 7 días y no había refresh. Ahora: (1) parser de historial con columnas reales + `next_fight_date`; (2) `_is_data_fresh` con piso `FIGHTER_MIN_RECHECK_MINUTES`=30, stale si `next_fight_date < date.today()`, techo `FIGHTER_MAX_AGE_HOURS`=24; (3) `GET /fighter/{name}?refresh=true` y `force_refresh` en `/predict`; (4) cache de `/predict` leída DESPUÉS de obtener datos, key `prediction:{n0}:{n1}:{s0}:{s1}` con los `last_updated`; (5) frontend: al resolver un peleador llama `GET /fighter/{name}` (`verifyFighterFreshness`, guard `searchState.verifiedName`), sello "Datos de UFCStats: hace X · pelea hoy", botón "Actualizar" (`refreshFighter`). Verificado en vivo por Muad'Dib: refresh forzado 4.2 s, CSV con la columna nueva, key de Redis con stamps, 63 tests verdes.

## Qué mirar (profundidad alta en 1–4, pasada real en 5)
1. `_is_data_fresh` / `_parse_last_updated` / `get_fighter_data`: casos borde (NaN, `last_updated` futuro por reloj, `next_fight_date` inválida, `force_refresh` con scrape fallido → fallback a datos viejos), consistencia entre piso/regla/techo, comportamiento bajo Docker en UTC vs CSV escrito en hora local.
2. Cache versionada: orden de pares (nombre, stamp) al invertir a/b; `_swap_cached_prediction` sigue correcto; ningún camino sirve una predicción con datos reemplazados; TTL; qué pasa si `last_updated` falta en un peleador.
3. Parser del historial: filas `next` con 3 celdas y con 10, filas normales, header, celdas sin `<p>`; que `next_fight_date` sea `None` (no ausente) cuando no hay fila `next`; que `_update_or_add_to_csv` limpie la fecha vieja.
4. Frontend: carreras entre `searchFighter`/`selectSuggestion`/`verifyFighterFreshness`/`refreshFighter` (seq, verifiedName), fugas de estado al cambiar de peleador o borrar el input, XSS (todo por `textContent`?), IDs del DOM vs `index.html`, `Date.parse` del ISO sin zona y microsegundos, mensajes en español.
5. Tests: ¿cubren lo que dicen? ¿algún test depende de la hora/fecha real de forma frágil (p. ej. cerca de medianoche)? Docs: ¿CLAUDE.md describe el código real?

## Comandos (correlos y reportá salida)
- `venv/bin/python -m pytest tests/ -q` (esperado: todos passed)
- `node --check frontend/index.js`
- `cd api && ../venv/bin/python -c "import main"`
No hagas requests a internet. No levantes uvicorn. No toques `api/.env`.

## Formato de salida
Lista de hallazgos: `SEVERIDAD (BLOCKER/HIGH/MEDIUM/LOW) — archivo:línea — qué falla, cómo reproducir, fix sugerido`. Solo BLOCKER/HIGH bloquean el consenso. Cerrá con la línea exacta `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS`.
