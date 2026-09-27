# Plan: Frescura de datos de peleadores (2026-09-26, noche)

Reporte del owner: la UI muestra a Raul Rosas Jr. 12-1-0 cuando "en este momento tiene una pelea ganada extra" (peleó esta noche vs Raoni Barcelos, UFC Fight Night 26-sep-2026).

## Diagnóstico (Muad'Dib, verificado en vivo ~20:50)
- UFCStats todavía publica `Record: 12-1-0` y muestra la pelea de hoy como `next` en el perfil → la fuente no tiene el resultado aún; ningún cambio de código puede mostrar 13-1-0 antes de que UFCStats actualice.
- Pero cuando actualice, la app lo ocultaría: CSV "fresco" 7 días (`_is_data_fresh(days=7)`), Redis 1 h con una key que no depende de los datos, `/search` (lo que ve la UI bajo el input) nunca scrapea, y no existe refresh manual.
- Además el parser de `fight_history` mapeaba mal las columnas (`'event': '00', 'date': '810'`): la app no sabía que el peleador tenía una pelea programada.

## Fase 1 — Backend (HalJordan, brief `.collab/briefs/fighter-freshness-backend.md`)
- [x] Parser de historial correcto + `next_fight_date` desde la fila `next` del perfil.
- [x] Frescura por reglas: piso `FIGHTER_MIN_RECHECK_MINUTES` (30), stale si `next_fight_date < hoy`, techo `FIGHTER_MAX_AGE_HOURS` (24; antes 7 días fijos).
- [x] `GET /fighter/{name}?refresh=true` y `force_refresh` en `/predict`; respuesta de `/fighter` con `last_updated`, `next_fight_date`, `data_age_seconds`.
- [x] Cache de `/predict` keyed por `last_updated` de ambos peleadores (se invalida sola al refrescar datos).
- [x] Tests: parser (fixture Rosas Jr.), reglas de frescura, force refresh, cache key, esquema CSV.

## Fase 2 — Frontend (Muad'Dib, skill `mma-ui-theme`)
- [x] Al resolver un peleador (exacto/único/seleccionado) llamar `GET /fighter/{name}` para pasar por las reglas de frescura y mostrar "Datos de UFCStats: hace X".
- [x] Botón "Actualizar" por corner → `?refresh=true` (spinner, récord y sello nuevos, errores inline).
- [x] Aviso "pelea hoy" cuando `next_fight_date` es hoy.

## Fase 3 — Cierre
- [x] pytest completo verde (67); API reiniciada; `curl '/fighter/Raul%20Rosas%20Jr.?refresh=true'` re-scrapea (4.2 s) y devuelve `next_fight_date: 2026-09-26`; `/predict` sin LLM cambia de key al refrescar (y por `title_fight`/`include_llm_analysis`); smoke en Chrome (verificación al resolver + botón "Actualizar").
- [x] Review de HalJordan sobre el diff completo → consenso (R1 BLOCKERS → R2 BLOCKERS → R3 NO BLOCKERS + confirmación) → commit (identidad del owner, sin trailers).
- [x] CLAUDE.md → AGENTS.md sincronizados; skill `mma-ui-theme` (contrato de IDs) y `tasks/lessons.md` actualizados; memoria actualizada.

**Review (gate de consenso Muad'Dib ↔ HalJordan):**
- Ejecución backend: HalJordan, registro `.collab/delegations/20260927T022305Z-*` (63 tests verdes, `import main` OK). Frontend + docs: Muad'Dib. Verificación en vivo (Muad'Dib): `?refresh=true` re-scrapea en 4.2 s y guarda `next_fight_date=2026-09-26`; CSV con la columna nueva; key de Redis con stamps; botón "Actualizar" en Chrome → "hace un momento · pelea hoy".
- R1 (`.collab/briefs/fighter-freshness-review.md`, registro `20260927T023405Z`): **BLOCKERS** — HIGH key de cache sin `title_fight`/`include_llm_analysis` (preexistente, pero se corrige ya que se rehacía la key); HIGH carrera de `verifiedName` en el frontend (volver al mismo nombre con la verificación en vuelo la saltaba y dejaba el spinner); MEDIUM `last_updated` futuro tratado como fresco; MEDIUM ISO con zona → 500 en `/fighter`; MEDIUM respuesta sin sello dejaba el botón deshabilitado; LOW fechas del parametrize fijadas en la recolección. Los 6 corregidos por Muad'Dib (key `:title=:llm=`, `verifyingName`/`verifySeq`, edad negativa → stale, normalización a hora local naive, `applyFighterResponse` siempre cierra el loading, offsets de días dentro del test) → 67 tests verdes, keys distintas en Redis para title_fight false/true.
- R2 (`.collab/briefs/fighter-freshness-review-r2.md`, registro `20260927T024328Z`): **BLOCKERS** — 5 de 6 resueltos; queda 1 HIGH: verificar X, pasar a Y y volver a X con Y en vuelo dejaba el sello en "Verificando…" (X seguía marcado como verificado). Fix Muad'Dib: `verifiedName` se invalida al empezar a verificar otro peleador (volver a X re-consulta `/fighter`, ms si está fresco).
- R3 (`.collab/briefs/fighter-freshness-review-r3.md`, registro `20260927T024809Z`): **NO BLOCKERS** sobre el fix del HIGH de R2. Mientras corría, Muad'Dib detectó en autorevisión un caso análogo (refresh en vuelo + reescribir el mismo nombre → la verificación se saltaba y el sello quedaba en "Actualizando…") y aplicó un fix de una línea (`refreshFighter` invalida `verifiedName` al empezar) DESPUÉS del veredicto; se pidió a HalJordan una confirmación acotada a esa línea (`.collab/briefs/fighter-freshness-review-r3-confirm.md`, registro `20260927T025102Z`): **NO BLOCKERS** (7 escenarios resueltos).
- **Consenso alcanzado** (tests: 67 passed corridos por Muad'Dib sobre el árbol final; review sin bloqueantes sobre el diff final) → commit con la identidad del owner, solo los archivos de esta tarea (los de la tarea gpt-6-luna en curso quedan fuera: `api/llm_client.py`, `tests/test_llm_client.py`, `README*`, sus hunks de `CLAUDE.md`/`AGENTS.md`/`tasks/todo.md`). Ningún run de Codex quedó activo. En vivo, tras publicar UFCStats el resultado, el botón "Actualizar" mostró 13-1-0 para Rosas Jr. y 22-6-0 para Barcelos.
- Pendiente del owner: redeploy al homelab (`rsync` + `docker compose up -d --build`; el `.env` del server puede fijar `FIGHTER_MAX_AGE_HOURS`/`FIGHTER_MIN_RECHECK_MINUTES`) y push.

---

# Plan: Búsqueda/carga de peleadores — concurrencia + scraper + UI (2026-09-26)

**Síntoma reportado (owner):** "no encuentro a los peleadores (probar con las peleas de hoy), y aunque aparezcan no cargan bien".
**Diagnóstico (Muad'Dib, con evidencia en vivo contra la API local):**
1. UFCStats sirve desde ~2026-07 un interstitial JS ("Checking your browser…": proof-of-work sha256 sobre `nonce:n`, `POST /__c`, cookie `_fmc`) → el scraper ve 0 filas → ningún peleador nuevo (p. ej. la cartelera de hoy, UFC Fight Night Rosas Jr. vs Barcelos) puede agregarse; `/predict` → 404 "not found".
2. El parser de perfil NUNCA funcionó (busca `b-list__box-item-value`, que no existe en el HTML) → los 37 peleadores del CSV tienen stats default 50/55/40/70 y edad 30.
3. Los 37 peleadores están stale (>7 días) → cada `/predict` scrapea 2 veces con `requests` síncrono dentro de `async def` → bloquea el event loop (medido: `/search` tarda 0.30 s vs 0.002 s durante un predict cuyo scrape falla rápido; con el scraper arreglado serían varios segundos de congelamiento de la búsqueda del otro peleador).
4. `/search/fighters/(` → 500 (el query se trata como regex). Redis caído → `/predict` 500.
5. Frontend: un solo timer de debounce para ambos inputs (escribir en B cancela la búsqueda de A), respuestas fuera de orden pisan el resultado, y con 0 resultados el record anterior queda visible ("aparece" pero es otro peleador) → predict 404. Errores vía `alert()`.
6. La letra de búsqueda en UFCStats se toma de la última palabra: "Raul Rosas Jr." → 'J' (está bajo R).

**Roles:** Muad'Dib planea/verifica/integra + frontend · HalJordan implementa backend (scraper, API) y revisa el diff final · Owner: reactivar `OPENAI_API_KEY` al cerrar y redeploy al homelab.
**Restricción:** `OPENAI_API_KEY` comentada en `api/.env` (no gastar tokens); Ollama apagado → el análisis LLM devuelve el texto de error esperado.

## Fase 1 — Scraper (HalJordan, brief `.collab/briefs/fighter-lookup-scraper.md`)
- [x] 1.1 Fixtures offline en `tests/fixtures/` (challenge, lista R recortada, perfil Rosas Jr.) — Muad'Dib
- [x] 1.2 Resolver el challenge PoW de UFCStats en `MMADataCollector` (cookie en la `requests.Session`, un reintento por request)
- [x] 1.3 Parser de perfil real (valor = texto del `li` menos el título; DOB → age); letra por apellido sin sufijos Jr./Sr./III; match exacto antes que substring
- [x] 1.4 Rate limit 1 s entre requests; `print` → `logging`
- [x] 1.5 `tests/test_data_collection.py` verde (sin red)
- [x] 1.6 Verificación en vivo (Muad'Dib): `search_and_scrape_fighter("Raul Rosas Jr.")` → 12-1-0 con stats reales

## Fase 2 — API no bloqueante (HalJordan, brief `.collab/briefs/fighter-lookup-api.md`)
- [x] 2.1 `get_fighter_data` en threadpool (`run_in_threadpool`) y ambos peleadores en paralelo (`asyncio.gather`)
- [x] 2.2 Lock + escritura atómica del CSV; filas nuevas restringidas a las columnas del CSV
- [x] 2.3 Búsqueda con `regex=False` + strip + exacto case-insensitive; `/fighter/{name}` devuelve el nombre canónico
- [x] 2.4 Cache Redis tolerante a fallos (timeouts 2 s; warning y seguir sin cache)
- [x] 2.5 Verificación en vivo (Muad'Dib): `/search` responde en ms durante un `/predict` que scrapea; `/search/fighters/%28` → 200

## Fase 3 — Frontend (Muad'Dib, skill `mma-ui-theme`)
- [x] 3.1 Debounce y número de secuencia por input (no pisar resultados fuera de orden)
- [x] 3.2 Lista de sugerencias clickeable (nombre canónico → input); ocultar stats cuando no hay resultados
- [x] 3.3 Fallback "Buscar en UFCStats" (`GET /fighter/{name}`) cuando no hay resultados locales
- [x] 3.4 Errores inline (sin `alert()`)

## Fase 4 — Cierre
- [x] 4.1 pytest completo verde; paridad de `engineer_fight_features` (la probabilidad de Jon Jones vs Stipe cambia al refrescar stats reales: documentar)
- [x] 4.2 Smoke en navegador: `/ui/` → "Rosas" → sugerencia → "Barcelos" → predecir → resultado
- [x] 4.3 Review de HalJordan sin blockers (gate de consenso, máx. 3 rondas) → commit local
- [x] 4.4 CLAUDE.md + AGENTS.md sincronizados; `tasks/lessons.md` si hubo corrección

## Review (2026-09-26, cierre por consenso Muad'Dib ↔ HalJordan)

**Gate de consenso:** 3 rondas. R1 (`.collab/briefs/fighter-lookup-review.md`): BLOCKERS FOUND — 3 HIGH (Redis síncrono en el loop; `seq` solo al vencer el debounce; substring ambiguo en el scraper) + 3 MEDIUM + 2 LOW, todos aceptados y corregidos por Muad'Dib. R2 (`-r2.md`): BLOCKERS FOUND — 2 HIGH (`_search_in_database` elegía la primera coincidencia parcial; stats desconocidas guardadas como 0.0), aceptados; al verificar en vivo apareció además el bug de actualización de filas existentes (`df.loc[...] = lista` → los 37 peleadores viejos nunca se refrescaban), corregido con `CSV_PATH` testeable. R3 (`-r3.md`; la primera corrida se colgó en stdin y fue matada y relanzada, ver `.collab/delegations/20260927T005156Z-note.txt`): **NO BLOCKERS**, 1 LOW (tres `--` + un `0%` legítimo descartaba el cero) aplicado post-gate en una línea + test. Ejecutores: HalJordan implementó scraper y API (`20260927T001632Z`, `20260927T002255Z`); Muad'Dib hizo frontend, fixtures, tests de `main.py`, las correcciones de las rondas y la documentación.

**Evidencia (salidas reales):**
- `pytest tests/ -q` → 46 passed (15 LLM + 22 scraper offline + 9 main.py).
- Paridad: mismas filas stale de Jon Jones vs Stipe → `p=0.7760478854179382` == baseline (`engineer_fight_features` intacto). Con datos refrescados la probabilidad cambia por diseño (stats reales en vez de defaults).
- Concurrencia: 8 requests a `/search` durante un `/predict` que scrapea 2 peleadores nuevos (4.0 s) → 1–2 ms cada una (antes 300 ms bloqueadas con scrape fallido; habrían sido segundos con scrape real).
- Scraper en vivo: Raul Rosas Jr. 12-1-0 (age 21, 42/52/54/25), Raoni Barcelos 22-5-0, Rodolfo Vieira 12-5-0, Robert Bryczek 18-8-0, Osmanli/Akylbek (sin peleas UFC → defaults 50/55/40/70), "Topuria" → Ilia Topuria, "Rodriguez"/"Silva" ambiguos → 404, inexistente → None en 0.4 s. Jon Jones stale → refrescado 28-1-0 con stats reales.
- Robustez: `/search/fighters/%28` → 200 `[]`; Redis caído (`REDIS_URL` a puerto cerrado) → `/predict` 200 con warnings.
- UI en Chrome: sugerencias por corner, teclado ↑/↓/Enter, récord solo con match exacto/único, fallback "Buscar en UFCStats" (Vieira y Bryczek agregados desde la UI), predict end-to-end con 5 factores, errores inline en español; sin errores de consola.
- `data/fighters_complete.csv` quedó con 43 filas (6 peleadores de la cartelera de hoy + refresco de Jon Jones); es dato de runtime y NO va en el commit.

**Pendiente del owner:** reactivar `OPENAI_API_KEY` en `api/.env`; redeploy al homelab (`rsync` + `docker compose up -d --build`, plan de deploy más abajo); opcional: `git push`.

---

# Plan: Deploy al Home Lab vía Tailscale (2026-09-26)

**Objetivo:** copiar (NO mover) el proyecto al homelab (`simon@homelab`, Debian 13) y servirlo solo dentro del tailnet, accesible únicamente desde `macbook-pro-de-said` (extensible a más devices después).
**Roles:** Muad'Dib (Claude Code) planea/verifica/integra/opera el server · HalJordan (Codex) implementa el diff del repo y revisa · Owner: pasos humanos (sudo, admin console Tailscale) y desempates.
**Guardia:** un /loop verificador corre durante toda la ejecución (`tasks/deploy/verify_plan.sh`): la Mac no pierde ni altera archivos fuera del scope, el diff queda dentro del scope, el server no expone nada en 0.0.0.0 salvo sshd, funnel apagado, y los items se marcan solo con evidencia.

## Arquitectura destino
```
MacBook (tailnet) ──HTTPS──> tailscale serve (homelab:443) ──> 127.0.0.1:8000 api (docker)
                                                              ├─ /      health (igual que hoy)
                                                              ├─ /ui/   frontend estático (mismo origen)
                                                              └─ redis (red interna compose, sin puerto publicado)
ACL de Tailscale: solo el MacBook → homelab:443 (y :22 para admin)
```
Sin Ollama en el server (qwen2.5:7b no cabe en 6 GB); LLM = OpenAI, con degradación ya existente.

## Fase A — Repo (HalJordan implementa, Muad'Dib verifica, gate de consenso)
- [x] A1 `api/main.py`: Redis desde `REDIS_URL` (default `redis://localhost:6379/0`) y servir `frontend/` en `/ui` si el directorio existe
- [x] A2 `frontend/index.js`: `API_BASE_URL` = mismo origen, fallback a `http://localhost:8000` cuando se sirve en :3000 / file://
- [x] A3 `Dockerfile` (python:3.11-slim, deps pinneadas = venv que generó el pkl), `.dockerignore`, `compose.yaml` (api + redis, `127.0.0.1:8000`, `./data` montado rw, `./models` ro, `env_file: api/.env`, `restart: unless-stopped`, límites de memoria)
- [x] A4 Tests: pytest 15/15 + paridad local de /predict = 0.7760478854179382 + `docker compose config` válido
- [x] A5 Review de Codex sin blockers → commit local (sin push)
- [x] A6 CLAUDE.md + README sincronizados (sección Deploy Home Lab)

## Fase B — Prerrequisitos humanos (Owner)
- [x] B1 Despertar el homelab (abrir tapa) y confirmar `tailscale ping homelab` responde
- [x] B2 Llave SSH (paso 7 del plan del homelab): `ssh-copy-id` desde la Mac para que el agente pueda operar sin contraseña
- [x] B3 Correr como sudo `~/setup/mma_prereqs.sh` (Muad'Dib lo escribe): Docker oficial + compose plugin, rsync, `simon` al grupo docker, `tailscale set --operator=simon`, lid-switch=ignore
- [ ] B4 Admin console Tailscale: MagicDNS + HTTPS certs activos; ACL que restrinja homelab a solo el MacBook (policy lista en `tasks/deploy/tailnet-policy.hujson`)

## Fase C — Transferencia y despliegue (Muad'Dib)
- [x] C1 (antes: capturar baseline de listeners del server con verify_plan.sh) `rsync` (copia, sin `--delete`, sin tocar origen) a `~/apps/mma-stuff/` excluyendo venv/.git/.pytest_cache/api/.env; `.env` por scp con chmod 600
- [x] C2 `docker compose up -d --build`; health 200 en 127.0.0.1:8000 desde el server
- [x] C3 `tailscale serve --bg 8000` (nunca funnel); `ss -tln` sin nada nuevo en 0.0.0.0
- [x] C4 Desde la Mac: `https://homelab.<tailnet>.ts.net/` health + `/ui/` carga + /predict paridad
- [ ] C5 Verificar ACL: el acceso depende de la policy (cualquier device nuevo sin grant no entra)
- [x] C6 Mac intacta: manifest de baseline idéntico (salvo archivos del scope)

## Review
_(llenar al ejecutar)_

---

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
