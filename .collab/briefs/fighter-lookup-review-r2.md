# Brief (HalJordan, REVIEW read-only, ronda 2): fix de búsqueda/carga de peleadores

Tus hallazgos de la ronda 1 y lo que hizo Muad'Dib (todos aceptados):
1. HIGH Redis síncrono en `/predict` → `redis_client.get`/`setex` ahora corren con `await run_in_threadpool(...)` dentro del mismo `try/except redis.RedisError` (`api/main.py`).
2. HIGH `seq` solo cambiaba al vencer el debounce → ahora `state.seq++` en CADA evento `input` (invalida al instante búsquedas y lookups en vuelo) y `lookupFighterOnUfcStats` revalida `seq` también después de `await response.json()` (`frontend/index.js`).
3. HIGH substring ambiguo → sin match exacto, el substring solo se acepta si es ÚNICO; con 2+ candidatos loguea warning y devuelve `None` (la UI ya muestra "No encontrado en UFCStats. Prueba con el nombre completo."). Tests nuevos: `test_ambiguous_substring_returns_none_without_profile_get` ("Rodriguez" → Paul y Ricco) y `test_unique_substring_is_accepted` ("Radach").
4. MEDIUM sugerencias viejas al reenfocar → `clearSuggestions()` vacía estado + DOM en 0 resultados, errores y `clearFighterUI`.
5. MEDIUM fallo de `/search` dejaba stats viejas → en error (si `seq` vigente) se ocultan stats, se limpian sugerencias y se muestra el aviso inline `is-error`.
6. MEDIUM rate limit parcial → `_throttle()` global a nivel de módulo (lock + `time.monotonic()`): ≥ `request_delay` entre requests consecutivos a UFCStats, cubriendo GET challenge → POST `/__c` → GET y scrapes paralelos en threads distintos (comparten `_last_request_at`). Tests: `test_rate_limit_between_list_and_profile` (1 espera ≈ 1.0 s) y `test_rate_limit_covers_challenge_round_trip` (3 esperas). CLAUDE.md corregido.
7. LOW ~37 filas → CLAUDE.md dice ~41 (2026-09-26). LOW `innerHTML` de key factors → construido con `createElement`/`textContent`.

Evidencia de Muad'Dib tras los cambios: `pytest tests/ -q` → 32 passed; `node --check frontend/index.js` OK; API reiniciada y smoke en vivo (`/search` en ms durante `/predict` con scraping; `/fighter/Rodriguez` → 404 por ambigüedad; `/fighter/Osmanli` → 200 (Mahammadali Osmanli, substring único)).

Revisá SOLO el diff no commiteado actual (`git diff` + untracked, EXCEPTO `.collab/delegations/*-stdout.log`, `tasks/deploy/`, `.agents/`, `.codex/`, `AGENTS.md`), confirmando que cada hallazgo quedó resuelto sin introducir regresiones (contratos: 16 features, `probabilities[1]`, cache key/swap, Pydantic, IDs del DOM, `search_and_scrape_fighter` nunca lanza). NO edites nada. NO leas `api/.env`. Sin servidor ni internet (podés correr pytest). Mismo formato con severidad y `archivo:línea`; solo BLOCKER/HIGH lo realmente en scope con escenario reproducible. Última línea exacta: `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS FOUND`.
