# Brief (HalJordan): REVIEW ronda 2 — frescura de datos de peleadores (solo lectura)

Segunda ronda del gate de consenso. NO edites archivos. Verificá que cada hallazgo de tu ronda 1 quedó resuelto y que las correcciones no introdujeron regresiones. Hallazgos con severidad + evidencia (archivo:línea); solo BLOCKER/HIGH bloquean.

## Alcance (idéntico a la ronda 1)
`git diff -- api/main.py scripts/data_collection.py tests/test_data_collection.py tests/test_main_csv.py frontend/index.html frontend/index.js frontend/styles.css` + `tests/test_main_freshness.py` (nuevo) + hunks de frescura de `CLAUDE.md`. Fuera de alcance: `api/llm_client.py`, `tests/test_llm_client.py`, `README*`, `data/`, `AGENTS.md`, `tasks/`, `.collab/`, y los hunks de gpt-6-luna de `CLAUDE.md` (otra tarea en curso).

## Qué se corrigió tras tu ronda 1 (verificá cada punto)
1. HIGH cache key sin opciones → `_normalize_cache_key(..., title_fight, include_llm_analysis)` agrega `:title={0|1}:llm={0|1}`; `predict_fight` pasa `request.title_fight` y `request.include_llm_analysis`. Test `test_cache_key_tracks_request_options_that_change_the_response`; `test_predict_cache_is_checked_after_fighter_refresh` ajustado (el request usa `include_llm_analysis=False`). Verificado en vivo por Muad'Dib: dos keys distintas en Redis para title_fight false/true.
2. HIGH carrera `verifiedName` (frontend/index.js, `verifyFighterFreshness`) → estado separado: `verifiedName` = verificación COMPLETADA; `verifyingName` + `verifySeq` = en vuelo. Volver al mismo nombre antes de la respuesta adopta la llamada en curso (`verifySeq = seq`) en vez de saltarla; al responder: si `verifyingName !== name` → la reemplazó otra (descartar); si `verifySeq !== state.seq` → el usuario cambió/borró (descartar sin marcar verificado); si no → `verifiedName = name` + pintar. `refreshFighter` limpia `verifyingName` al terminar. Revisá esta máquina de estados con los escenarios: (a) escribir X, editar, volver a X antes de la respuesta; (b) X en vuelo → cambiar a Y; (c) X en vuelo → borrar el input; (d) X en vuelo → click "Actualizar".
3. MEDIUM `last_updated` futuro → `_is_data_fresh`: `age < 0` → stale (log). Casos nuevos en el parametrize (`timedelta(hours=-5)` con y sin pelea ayer).
4. MEDIUM ISO con zona → `_parse_last_updated` convierte a hora local naive (`astimezone().replace(tzinfo=None)`); `GET /fighter` ya no puede romper la resta. Test `test_timezone_aware_last_updated_is_normalized_to_local_naive`.
5. MEDIUM respuesta de `/fighter` sin sello → `applyFighterResponse` SIEMPRE llama `setFreshnessState(..., 'idle', describeFreshness(...))` (y `updateFighterStats` ya no toca el sello).
6. LOW fechas fijadas en la recolección → el parametrize usa offsets de días y construye `date.today()` DENTRO del test.

## Comandos
- `venv/bin/python -m pytest tests/ -q -s -p no:cacheprovider` (si tu sandbox no da temporal, reportá cuáles corrieron; Muad'Dib corrió la suite completa: 67 passed).
- `node --check frontend/index.js`
- `cd api && ../venv/bin/python -c "import main"`
Sin internet, sin uvicorn, sin tocar `api/.env`.

## Formato
`SEVERIDAD — archivo:línea — qué falla, cómo reproducir, fix sugerido` por hallazgo (o "resuelto" por cada punto 1–6). Cerrá con la línea exacta `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS`.
