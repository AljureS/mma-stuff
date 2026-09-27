---
name: mma-run-stack
description: Levanta y verifica el stack completo del MMA Fight Predictor (Redis + API FastAPI + frontend + Ollama opcional). Usa esta skill SIEMPRE que necesites correr la app, probar un endpoint en vivo, hacer un smoke test, verificar que un cambio funciona de verdad, o diagnosticar por qué la API "no responde" — incluso si el usuario solo dice "levanta el servidor", "prueba la API", "corre el proyecto" o "¿funciona esto?".
---

# Levantar el stack del MMA Fight Predictor

Todo se ejecuta desde la raíz del proyecto (`/Users/saidaljure/Documents/2026/mma-stuff`). El Python correcto es el del venv de la raíz: `venv/bin/python` — no uses el python del sistema, no tiene las dependencias.

## Orden de arranque (importa)

### 1. Redis — obligatorio
La API asume `localhost:6379` (hardcodeado en `api/main.py`, no lee `REDIS_URL`). Sin Redis la API arranca pero `/predict` falla al cachear.

```bash
redis-cli ping 2>/dev/null || redis-server --daemonize yes
redis-cli ping   # debe responder PONG
```

### 2. Artefactos de datos — solo si faltan
La API necesita `models/mma_prediction_model.pkl` y `data/fighters_complete.csv` al arrancar (startup event). Si falta cualquiera:

```bash
venv/bin/python scripts/setup_dev_data.py   # regenera modelo dummy + CSV seed
```

Ojo: esto SOBREESCRIBE el CSV con los 20 peleadores seed — los peleadores agregados por auto-scraping se pierden. Solo correrlo si de verdad faltan los archivos.

### 3. API
```bash
cd api && ../venv/bin/python main.py
```
Levanta uvicorn en `0.0.0.0:8000` (hardcodeado, no lee `API_HOST`/`API_PORT`). Docs interactivas en `http://localhost:8000/docs`. Para dejarla corriendo mientras haces otra cosa, córrela en background y guarda el log.

### 4. Frontend — servidor estático cualquiera
```bash
python3 -m http.server 3000 --directory frontend
```
`frontend/index.js` apunta a `http://localhost:8000` (hardcodeado). CORS está en `*`, así que cualquier puerto sirve.

### 5. Ollama — opcional (solo fallback LLM)
Sin `OPENAI_API_KEY` en `api/.env` o si OpenAI falla, el análisis LLM usa Ollama:
```bash
ollama serve &
ollama pull qwen2.5:7b
```
Si no hay ni OpenAI ni Ollama, la API sigue funcionando — el campo de análisis LLM devuelve un mensaje de error genérico, nunca rompe `/predict`.

## Verificación (en este orden)

```bash
# 1. Salud general: debe reportar models_loaded=true y fighters_count>0
curl -s http://localhost:8000/ | python3 -m json.tool

# 2. Estado LLM y circuit breakers
curl -s http://localhost:8000/health/llm | python3 -m json.tool

# 3. Búsqueda (no toca red externa)
curl -s "http://localhost:8000/search/fighters/jon" | python3 -m json.tool

# 4. Predicción SIN LLM — el smoke test principal (rápido, sin costo de tokens)
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"fighter_a": "Jon Jones", "fighter_b": "Stipe Miocic", "include_llm_analysis": false}' \
  | python3 -m json.tool
```

Para smoke tests usa siempre `include_llm_analysis: false`: es rápido, no gasta tokens y aísla el pipeline ML del pipeline LLM. Usa peleadores que YA están en el CSV (Jon Jones, Stipe Miocic, Islam Makhachev...) — un nombre desconocido dispara scraping real a UFCStats (lento, red externa, y escribe en el CSV).

## Problemas comunes

| Síntoma | Causa | Fix |
|---|---|---|
| `Connection refused` en :8000 | API no arrancó — revisa su log | Buscar traceback de startup (pkl/CSV faltante es lo típico) |
| Puerto 8000 ocupado | Instancia vieja viva | `lsof -ti:8000 \| xargs kill` |
| `/predict` lanza error de Redis | redis-server caído | `redis-server --daemonize yes` |
| Predicción tarda >30s | Está scrapeando UFCStats (peleador nuevo) o esperando LLM | Normal; usa peleadores del CSV y `include_llm_analysis: false` |
| Análisis LLM = mensaje de error | Sin OPENAI_API_KEY ni Ollama | Es diseño, no bug: el fallback degrada elegante |
| El CSV aparece modificado en git | La API escribe en él en runtime | Normal y documentado; no es corrupción |

## Apagar
```bash
lsof -ti:8000 | xargs kill 2>/dev/null   # API
lsof -ti:3000 | xargs kill 2>/dev/null   # frontend
redis-cli shutdown nosave 2>/dev/null    # Redis (nosave: la cache es descartable)
```
