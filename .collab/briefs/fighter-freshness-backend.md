# Brief (HalJordan): frescura de datos de peleadores — refresh forzado, regla post-pelea y cache que sigue a los datos

Objective: que la API vuelva a scrapear a un peleador cuando su información puede haber cambiado (peleó después del último scrape, o el usuario pide refrescar) y que `/predict` nunca sirva una predicción cacheada calculada con datos viejos. Hoy el récord de Raul Rosas Jr. queda congelado 7 días aunque UFCStats lo actualice esa misma noche.

## Diagnóstico (verificado en vivo por Muad'Dib 2026-09-26 ~20:50; no re-investigar)
- UFCStats hoy muestra `Record: 12-1-0` para Raul Rosas Jr.; la primera fila del historial de su perfil es `next` = "UFC Fight Night: Rosas Jr. vs. Barcelos — Sep. 26, 2026" (la pelea es esta noche; UFCStats publica el resultado horas después). La app no puede mostrar 13-1-0 hasta que la fuente actualice, pero cuando lo haga el CSV la ocultaría hasta 7 días (`_is_data_fresh(days=7)` en `get_fighter_data`), y Redis 1 h más (la key `prediction:{a}:{b}` no depende de los datos).
- `get_fighter_detailed_stats` parsea mal el historial: las columnas de la tabla son `W/L, Fighter, Kd, Str, Td, Sub, Event, Method, Round, Time` (10 `td`; la fila `next` tiene solo 3: `W/L, Fighter, Event`), pero el código toma `cells[2..6]` como event/date/method/round/time → en el CSV quedó `'event': '00', 'date': '810'`. Cada `td` trae uno o dos `<p class="b-fight-details__table-text">`: en Fighter son [peleador, oponente]; en Event son [nombre, fecha `Mar. 07, 2026`] (en la fila `next`: [`Matchup Preview`, nombre, fecha]); en Method [método, detalle].
- No hay forma de forzar un refresh ni desde la API ni desde la UI.

## Cambios exactos

### `scripts/data_collection.py`
1. `get_fighter_detailed_stats`: reescribir el parseo del historial. Para cada `tr.b-fight-details__table-row`: `cells = tr.find_all('td')`; si no hay celdas (header) se salta. `texts = [[p.get_text(strip=True) for p in td.find_all('p')] or [td.get_text(strip=True)] for td in cells]`. Helper local `pick(i, j)` que devuelve `texts[i][j]` o `''` si no existe (nunca IndexError). Fila normal (≥10 celdas): `result=pick(0,0)`, `opponent=pick(1,1)`, `event=pick(6,0)`, `date=pick(6,1)`, `method=pick(7,0)`, `round=pick(8,0)`, `time=pick(9,0)`. Fila `next` (`pick(0,0) == 'next'`, 3 celdas): `event` = penúltimo elemento de `texts[2]`, `date` = último; `method`/`round`/`time` = `''`. Mantener el dict con exactamente las 7 claves actuales (`result, opponent, event, date, method, round, time`), `date` como texto crudo.
2. Nuevo helper `_parse_fight_date(text)` → `datetime.strptime(text, '%b. %d, %Y').date().isoformat()`; `None` si no parsea.
3. `stats['next_fight_date']`: fecha ISO (`'2026-09-26'`) de la fila `next` si existe y parsea; si no hay fila `next`, `None`. La clave va SIEMPRE en el dict devuelto (para que el CSV borre la fecha vieja cuando la fila `next` desaparece). Verificar que `search_and_scrape_fighter` mezcla `detailed_stats` en el dict final (hoy hace `update`) para que la clave llegue a `main.py`.

### `api/main.py`
4. Config por env, leída a nivel de módulo con `os.getenv`: `FIGHTER_MAX_AGE_HOURS` (default `24`; antes 7 días fijos) y `FIGHTER_MIN_RECHECK_MINUTES` (default `30`). Si el valor no parsea a float → default + `logger.warning`.
5. `_is_data_fresh(fighter) -> bool` (quitar el parámetro `days`; actualizar los call sites):
   - `last_updated` ausente, NaN (pandas lo entrega como `float('nan')`) o no parseable → `False`.
   - `age = datetime.now() - last_updated`; si `age < FIGHTER_MIN_RECHECK_MINUTES` → `True` (piso: aunque haya una pelea pasada, no re-scrapear a cada request mientras UFCStats no actualiza).
   - si `next_fight_date` (str ISO; usar `_nan_to_none`) parsea y es `< date.today()` → `False` con `logger.info("%s fought on %s after last update: stale", ...)`. El día de la pelea NO cuenta como stale (el resultado sale horas después; para eso está el refresh manual).
   - si `age >= FIGHTER_MAX_AGE_HOURS` → `False`; si no → `True`.
6. `get_fighter_data(fighter_name, force_refresh=False)`: calcular una sola vez `reason` (`'not found'` / `'stale'` / `'forced refresh'` / `None` si fresco y no forzado) en lugar del doble `if` actual; con `reason` → scrapear como hoy (mismo lock, misma actualización del CSV, misma recarga, mismo retorno por nombre canónico, mismo fallback a datos viejos si el scrape falla). Loguear el `reason`.
7. `_update_or_add_to_csv`: antes de actualizar/agregar, garantizar la columna: `if 'next_fight_date' not in df.columns: df['next_fight_date'] = None` (el CSV actual no la tiene). El resto del esquema no cambia; `None` se escribe vacío.
8. `GET /fighter/{fighter_name}`: nuevo query param `refresh: bool = False` → `await run_in_threadpool(get_fighter_data, fighter_name, refresh)`. `FighterStatsResponse` gana tres campos opcionales (compatibles hacia atrás): `last_updated: Optional[str] = None` (el ISO del CSV), `next_fight_date: Optional[str] = None` y `data_age_seconds: Optional[float] = None` (= `(datetime.now() - last_updated).total_seconds()`, calculado en el servidor para que el frontend no dependa de la zona horaria del servidor; `None` si no parsea). `stats` sigue siendo la fila saneada completa.
9. `FightPredictionRequest`: nuevo campo `force_refresh: bool = False`; pasarlo a las dos llamadas de `get_fighter_data` en `predict_fight`.
10. Cache de `/predict` que sigue a los datos: mover la lectura del cache DESPUÉS de obtener `fighter_a_data`/`fighter_b_data` y de la validación 404. Nueva firma `_normalize_cache_key(fighter_a, fighter_b, stamp_a='', stamp_b='')` → `prediction:{n0}:{n1}:{s0}:{s1}`, ordenando los pares (nombre normalizado, stamp) juntos por nombre; stamps = `str(_nan_to_none(data.get('last_updated')) or '')`. Así un scrape nuevo (por regla o por `force_refresh`) invalida solo la predicción de esos datos. La lógica de swap por orden a/b (`_swap_cached_prediction`) se mantiene igual; TTL sigue 3600 s; el `setex` usa la misma key.
11. NO tocar: el vector de 16 features, `probabilities[1]` = fighter_a, `_swap_cached_prediction`, el prompt LLM, `/search/fighters`, el mount de `/ui`, CORS, el bloque `__main__`, `_sanitize_csv_record`/`_nan_to_none`, `_search_in_database`.

### Tests
12. `tests/test_data_collection.py`: (a) con la fixture `ufcstats_fighter_rosas_jr.html`, `get_fighter_detailed_stats` devuelve `next_fight_date == '2026-09-26'`, `fight_history[0] == {'result': 'next', 'opponent': 'Raoni Barcelos', 'event': 'UFC Fight Night: Rosas Jr. vs. Barcelos', 'date': 'Sep. 26, 2026', 'method': '', 'round': '', 'time': ''}` y `fight_history[1]` = `{'result': 'win', 'opponent': 'Rob Font', 'event': 'UFC 326: Holloway vs. Oliveira 2', 'date': 'Mar. 07, 2026', 'method': 'U-DEC', 'round': '3', 'time': '5:00'}`; (b) quitando la fila `next` del HTML en memoria → `next_fight_date is None` y `fight_history[0]['result'] == 'win'`. `test_profile_parser_only_returns_csv_stats_and_age` sigue pasando ajustando el conjunto esperado de claves (+`next_fight_date`).
13. Nuevo `tests/test_main_freshness.py` (mismo patrón que `tests/test_main_search.py`: importa `main`, sin Redis ni servidor): `_is_data_fresh` — actualizado hace 2 h sin pelea → fresco; hace 30 h → stale; `next_fight_date` ayer + `last_updated` hace 2 h → stale; `next_fight_date` ayer + `last_updated` hace 5 min → fresco (piso); `next_fight_date` hoy → fresco; `next_fight_date` NaN/None → solo cuenta la edad; `last_updated` NaN → stale. `get_fighter_data('Jon Jones', force_refresh=True)` con datos frescos en `fighter_database` llama al collector igual (monkeypatch `data_collection.MMADataCollector.search_and_scrape_fighter` → dict con `name: 'Jon Jones', wins: 29, ...`; `main.CSV_PATH` → CSV temporal con esa fila) y devuelve `wins == 29`; sin `force_refresh` y fresco NO llama al collector. `_normalize_cache_key`: mismo resultado al invertir a/b (con sus stamps), distinto al cambiar un stamp.
14. `tests/test_main_csv.py`: `test_add_new_fighter_keeps_csv_schema` ahora espera `COLUMNS + ['next_fight_date']`; nuevo caso: actualizar un peleador existente con `next_fight_date: None` deja la celda vacía (NaN) donde antes había una fecha.

## Archivos que te pertenecen (no edites nada más)
`scripts/data_collection.py`, `api/main.py`, `tests/test_data_collection.py`, `tests/test_main_csv.py`, `tests/test_main_freshness.py` (nuevo).

## Contexto a leer primero
`AGENTS.md` (secciones "Componente 1", "Datos de peleadores con auto-scraping", "Componente 3"), `api/main.py`, `scripts/data_collection.py`, `tests/test_data_collection.py`, `tests/test_main_csv.py`, `tests/fixtures/ufcstats_fighter_rosas_jr.html` (tabla `b-fight-details__table`).

## No hacer
No tocar `frontend/`, `data/`, `models/`, docs (`CLAUDE.md`, `AGENTS.md`, `README*`), `tasks/`, `.env*`, `requirements.txt`, `.collab/`. No leer `api/.env`. No commitear. No hacer requests a internet. No levantar uvicorn (Muad'Dib hace la verificación en vivo). Muad'Dib está editando `frontend/` y docs en el mismo working tree en paralelo: ignorá esos cambios en `git status` y no los toques.

## Tests (verde = todo pasa)
- `venv/bin/python -m pytest tests/ -q` → todos passed (46 previos + los nuevos).
- `cd api && ../venv/bin/python -c "import main"` → sin error (Redis puede no estar).

## Reporte
Archivos cambiados, comandos corridos con resultado y el `git status` contra el que corrieron, lo que saltaste y por qué, preguntas abiertas. Última línea exacta: `DONE` o `BLOCKED: <motivo>`.
