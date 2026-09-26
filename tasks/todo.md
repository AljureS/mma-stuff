# Plan: Refactor Completo del MMA Fight Predictor

> Objetivo del refactor (definido por el usuario, 2026-07-01):
> 1. **Mantener la funcionalidad** que hoy funciona de verdad (predict, LLM, scraping, búsqueda, frontend).
> 2. **UI nueva con temática MMA real** (hoy es 100% genérica gris/azul).
> 3. **Borrar todo el slop**: código muerto, placeholders que mienten, docs duplicadas.
>
> Este archivo es el plan maestro. Marcar items al completarlos y documentar resultados en la sección Review.

## Fase 0 — Tooling: subagentes y skills (esta sesión)

Roster decidido tras escanear todo el repo con 3 agentes de auditoría (backend, scripts/data, frontend/docs).
Racional: el refactor tiene 4 flujos de trabajo (borrar slop, limpiar backend, rediseñar UI, consolidar docs) + 1 compuerta transversal (verificación). Cada subagente es un worker con un solo trabajo; cada skill es un procedimiento/conocimiento reutilizable. Las skills guardan el CÓMO (atemporal); este todo.md guarda el QUÉ (inventario puntual).

**Subagentes (`.claude/agents/`):**
- [x] `slop-auditor` — solo lectura; veredicto BORRABLE/NO BORRABLE con evidencia antes de cualquier eliminación
- [x] `backend-refactorer` — ejecuta cambios en api/ y scripts/ conociendo los contratos frágiles (vector de 16 features, probabilities[1]=fighter_a, CSV en runtime)
- [x] `mma-ui-builder` — reconstruye frontend/ con el design system MMA preservando IDs y contrato de API
- [x] `stack-verifier` — solo lectura+bash; levanta el stack, corre tests y checks de paridad; reporta PASS/FAIL, nunca arregla

**Skills (`.claude/skills/`):**
- [x] `mma-run-stack` — cómo levantar y verificar el stack completo (Redis, API, frontend, Ollama)
- [x] `slop-audit` — estándar de evidencia para borrar código sin romper nada + trampas conocidas del repo
- [x] `mma-ui-theme` — design system "Fight Night" (paleta corners, tipografía, componentes, reglas de compatibilidad)
- [x] `refactor-verify` — definición de "terminado": checklist de verificación antes de marcar cualquier fase
- [x] `sync-claude-md` — procedimiento para mantener CLAUDE.md como fuente de verdad tras cada cambio

- [x] Actualizar CLAUDE.md con la nueva estructura y el tooling

## Inventario de Slop (evidencia de las auditorías 2026-07-01)

### Archivos completos a borrar
| Item | LOC | Evidencia | Riesgo |
|---|---|---|---|
| `api/ml_system.py` | 331 | Nunca importado (grep repo-wide vacío); fuentes de datos simuladas. Las 16 features objetivo ya están documentadas en CLAUDE.md | Bajo |
| `scripts/deployment_setup.sh` | 768 | Configura PostgreSQL/Nginx/Systemd/SSL que el código no usa; Linux-only en proyecto macOS | Bajo |
| `database_schema.sql` | 55 | Nadie lo lee/ejecuta (deployment_setup.sh generaba su propio SQL inline) | Bajo |
| `ARCHITECTURE.md` | 114 | Duplica README/CLAUDE.md; referencia archivos inexistentes (`mma_frontend.html` ×3, CSVs fantasma) | Bajo |
| `IMPLEMENTATION_SUMMARY.md` | 336 | Doc histórico de la migración Claude→OpenAI; confunde como si fuera estado actual | Bajo |
| `dump.rdb`, `.DS_Store` | — | Artefactos de runtime/SO; agregar a .gitignore | Nulo |

### Código a borrar dentro de archivos
| Item | Ubicación | Evidencia |
|---|---|---|
| Import `LLMProvider` sin uso | `api/main.py:21` | Nunca referenciado en main.py |
| `POST /retrain` + background task | `api/main.py:297-335` | Cuerpo 100% comentado (no-op que devuelve "accepted") |
| `GET /events/upcoming` hardcodeado | `api/main.py:257-295` | Eventos ficticios con fecha ya pasada (2025-09-15); su consumidor en frontend es huérfano |
| `GET /analytics/*` (2 endpoints) | `api/main.py:337-366` | Métricas y ROI inventados |
| `get_betting_insights()` | `api/main.py:644-664` | Odds fijas -120/+100; borrar también su sección en UI |
| `get_recent_form()`, `get_current_ranking()` | `api/main.py:688-699` | Valores fijos; `/fighter/{name}` debe dejar de mentir |
| **JS duplicado inline** | `frontend/index.html:231-559` | Copia íntegra de index.js + carga el externo (doble mantenimiento) |
| `loadUpcomingEvents()` | `frontend/index.js:219-266` | `#upcomingEvents` no existe en el HTML; código inalcanzable |
| Métodos muertos de `MMADataCollector` | `scripts/data_collection.py` | `scrape_ufc_stats`, `scrape_sherdog_rankings`, `scrape_tapology_events`, `get_social_sentiment`, `_scrape_reddit_sentiment`, `_get_twitter_sentiment`, `get_betting_odds_historical` (YOUR_API_KEY), `save_data`, `main()` — ~230 LOC solo alcanzables desde un `main()` que nunca corre |
| Imports selenium | `scripts/data_collection.py:6-7` | `webdriver` y `By` importados, jamás usados (todo es requests+BS4) |
| Deps sin uso | `api/requirements.txt` | `psycopg2-binary`, `structlog`, `python-jose`, `passlib`, `selenium`, `webdriver-manager`, `lxml` (verificar), `python-multipart` (revisar) |

### ⚠️ Verificar ANTES de borrar — RESUELTO por slop-auditor (2026-07-01)
- [x] `get_fighter_detailed_stats()`: **NO BORRABLE — es producción.** Cadena confirmada por lectura directa: `main.py:406-409` → `search_and_scrape_fighter` → `data_collection.py:100` llama `get_fighter_detailed_stats`. Viven también `_normalize_stat_name`/`_parse_stat_value` y los 4 parsers.
- [x] `/events/upcoming`: NO es huérfano del todo — **la copia inline (la viva) sí hace el fetch en cada carga** y descarta el resultado por un null-guard. Borrar endpoint + `UpcomingEvent` + JS (ambas copias) en el mismo cambio.
- [x] Vector de 16 features: confirmado contrato con el pkl (`setup_dev_data.py:14` entrena con `randn(1000, 16)`). El padding NO se borra.
- [x] **Hallazgo crítico del auditor:** la copia JS viva es la INLINE de index.html — el `index.js` externo nunca ejecuta (redeclaración de `const API_BASE_URL` → SyntaxError en parse). Al borrar el inline, index.js "se promueve": hay que borrarle `loadUpcomingEvents` (sin null-guard, haría TypeError) en el mismo cambio.
- [x] Deps: las 8 candidatas BORRABLES (incl. lxml — BS4 usa 'html.parser' explícito ×5; python-multipart — cero Form/File/UploadFile; webdriver-manager — cero refs). Bonus: imports muertos `asyncio`/`aiohttp` en main.py y `sys` duplicado (L703).
- [x] Response models: `FighterStatsResponse.recent_form` es REQUERIDO sin default → quitar campo al borrar el helper; `betting_insights` es Optional → sin fricción.

### Issues conocidos fuera del alcance del refactor (no tocar, solo documentar)
- El scraper de UFCStats devuelve 0 filas hoy (2026-07-01): el HTML del sitio cambió o bloquea el request. El fallback a datos stale funciona (por diseño), así que `/predict` sigue vivo. Arreglar el parser es feature work post-refactor.

### Se queda (funciona de verdad)
`api/main.py` (núcleo predict/search/fighter/health), `api/llm_client.py` (100% real, 15 tests), `search_and_scrape_fighter` + parsers de `data_collection.py`, `scripts/setup_dev_data.py`, `tests/`, `test_scraping.py` (prueba manual del scraper), CSV, pkl, frontend (rediseñado), README.md (corregido), README_LLM.md.

## Fase 1 — Limpieza backend — ✅ COMPLETADA 2026-07-01 (slop-auditor → backend-refactorer)
- [x] Capturar baseline: `/predict` Jon Jones vs Stipe = 0.7760478854179382 + `/` + `/search` (en `tasks/baselines/`)
- [x] Borrar `api/ml_system.py`, `database_schema.sql`, `scripts/deployment_setup.sh`
- [x] Limpiar `main.py` (711→590 LOC): fuera `/retrain`, `/events/upcoming`+`UpcomingEvent`, `/analytics/*` ×2, `get_betting_insights`+campo, `get_recent_form`+campo, `get_current_ranking`, imports muertos (LLMProvider, asyncio, aiohttp, BackgroundTasks, sys dup)
- [x] `/fighter/{name}`: `ranking` real desde CSV (NaN→None), sin `recent_form`
- [x] Limpiar `data_collection.py` (496→259 LOC): 8 métodos muertos + selenium/pandas/time/json; cadena de producción intacta
- [x] Podar `requirements.txt` (24→16): psycopg2, structlog, jose, passlib, selenium, webdriver-manager, lxml, multipart
- [x] Fix cache key Redis: key normalizada (sorted+lower) + `_swap_cached_prediction` (invierte probs y niega key_factors si el orden del request difiere del cacheado) — verificado sin cache cruzado
- [x] Fix search 500: `_nan_to_none`/`_sanitize_csv_record` en search y fighter — 200 verificado
- [x] `.gitignore` + borrados `dump.rdb`/`.DS_Store`
- [x] Verificación: pytest 15/15, paridad exacta, endpoints borrados → 404, startup limpio 37 peleadores

## Fase 2 — UI temática MMA — ✅ COMPLETADA 2026-07-01 (mma-ui-builder + skill mma-ui-theme)
- [x] JS inline duplicado eliminado (index.html 568→258 LOC; index.js única fuente — el inline era la copia VIVA)
- [x] `loadUpcomingEvents()` y `displayBettingInsights()` + sección betting eliminados (cero refs muertas, grep verificado)
- [x] Design system Fight Night aplicado: corners rojo/azul con VS en gradiente, oro solo para TITLE FIGHT, octágono girando como spinner, Barlow Condensed/Inter
- [x] Chart doughnut retematizado con colores de corner (#DC2626/#2563EB) + banner de ganador con glow (`winnerBanner`/`titleBeltNote` nuevos)
- [x] IDs preservados (cero huérfanos, check automatizado) y contrato de API intacto (paridad 0.7760478854179382 vía UI E2E)
- [x] Smoke en :3000 contra API real: 3 assets 200, `node --check` OK, search "jon" funciona
- [x] Skill mma-ui-theme retroalimentada: semántica del signo en key factors (age invertido, título=oro), clases dinámicas en styles.css (no Tailwind CDN), title_fight desde el request

## Fase 3 — Consolidación de docs — ✅ COMPLETADA 2026-07-01 (en paralelo con Fase 2)
- [x] README.md reescrito (157→65 líneas): sin drift, disclaimer del modelo dummy, apunta a CLAUDE.md como fuente de verdad
- [x] ARCHITECTURE.md e IMPLEMENTATION_SUMMARY.md borrados (veredicto BORRABLE del auditor)
- [x] CLAUDE.md sincronizado: Estado Actual post-refactor, árbol, tabla de 5 endpoints, flujo de /predict con cache swap, Componente 3 (ml_system) eliminado y renumerado, features objetivo preservadas como referencia, stack/pendientes actualizados, sección Frontend Fight Night
- [x] Skill sync-claude-md actualizada (números de componente)

## Fase 4 — Verificación final — ✅ PASS 2026-07-01 (stack-verifier, 14/14 checks)
- [x] pytest 15/15 (22.61s, cero errores de import tras borrados)
- [x] Paridad de `/predict` vs baseline: 0.7760478854179382 exacto, key_factors idénticos, sin betting_insights
- [x] Fix de cache verificado: pelea invertida servida desde cache normalizada con swap correcto (0.2240, ganador consistente, signos invertidos)
- [x] Stack completo arriba (restart fresco) + frontend smoke (assets 200, 4 scripts esperados, cero IDs huérfanos, cero refs muertas)
- [x] 404s esperados en los 4 endpoints borrados; search 200 (era 500); /fighter sin recent_form
- [x] Docs coherentes (grep: solo menciones históricas) y archivos borrados fuera de disco
- [x] CSV intacto (MD5 idéntico), ambiente restaurado (API nueva corriendo, Redis y :3000 intactos)

## Review (llenar al ejecutar)

### Cierre del refactor (2026-07-01) — LAS 4 FASES COMPLETADAS, VEREDICTO FINAL PASS

**Números:** main.py 711→590 LOC · data_collection.py 496→259 · index.html 568→258 · README 157→65 · requirements 24→16 deps · ~2,400 LOC eliminadas en total (código+docs+script deployment). Borrados 6 archivos (ml_system.py, deployment_setup.sh, database_schema.sql, ARCHITECTURE.md, IMPLEMENTATION_SUMMARY.md, dump.rdb) y 4 endpoints placeholder.

**Funcionalidad:** paridad exacta con baseline (0.7760478854179382), 15/15 tests, y DOS bugs arreglados de regalo: search 500 (NaN en JSON) y cache key sin normalizar (con swap correcto de probabilidades/factores). El buscador del frontend funciona por primera vez.

**Orquestación:** slop-auditor (veredictos con evidencia; corrigió un falso-muerto de la auditoría inicial: get_fighter_detailed_stats ES producción, y descubrió que la copia JS viva era la inline) → backend-refactorer (4 cambios atómicos verificados) → mma-ui-builder (Fight Night e2e, retroalimentó el design system) → stack-verifier (PASS 14/14). Docs en paralelo con Fase 2 desde el main loop con la skill sync-claude-md.

**Deuda que queda (consciente y documentada):** modelo dummy (pendiente #1), 10/16 features con padding (contrato con el pkl), scraper UFCStats devuelve 0 filas (issue pre-existente), Redis/uvicorn hardcodeados, `on_event` deprecado en FastAPI. Sin commit aún — el working tree tiene todo el refactor listo para revisión del usuario.

### Fase 0 (2026-07-01) — COMPLETADA
- Baseline pre-refactor: pytest 15/15 PASSED (22.7s).
- Auditoría con 3 agentes Explore en paralelo (backend / scripts+data / frontend+docs): ~50% código vivo, ~15% placeholder, ~35% muerto (~700 LOC). Hallazgo no documentado antes: index.html duplica TODO index.js inline (L231-559).
- Creados 4 subagentes (`.claude/agents/`) y 5 skills (`.claude/skills/`), siguiendo la metodología del plugin skill-creator (leída de su SKILL.md; el plugin no estaba habilitado como skill invocable — ver lessons.md).
- CLAUDE.md sincronizado: árbol de estructura + sección "Tooling de Refactor".
- Pendiente opcional de la metodología skill-creator: correr el loop de evals de las skills (test prompts con/sin skill + viewer) cuando el usuario quiera iterarlas.
