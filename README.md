# MMA Fight Predictor

Predicción de peleas de MMA: una API FastAPI compara las estadísticas de dos peleadores, un modelo XGBoost calcula probabilidades de victoria y un LLM (OpenAI con fallback a Ollama local) genera el análisis cualitativo en español. Incluye frontend web con temática Fight Night y scraping automático de UFCStats para mantener frescos los datos de los peleadores.

> ⚠️ **El modelo actual es un dummy de desarrollo** (entrenado con datos aleatorios). Las probabilidades NO tienen valor predictivo real; no usar para apuestas. Entrenar el modelo real es el pendiente #1 del proyecto.

## Arquitectura

```
Navegador (frontend/, :3000)
    │  POST /predict
    ▼
FastAPI (api/main.py, :8000) ── cache ──> Redis (:6379)
    │        │
    │        ├─> XGBoost (models/mma_prediction_model.pkl) — 16 features → probabilidades
    │        ├─> LLM (api/llm_client.py): OpenAI gpt-4o-mini → fallback Ollama qwen2.5:7b
    │        └─> Scraper UFCStats (scripts/data_collection.py) si el peleador falta o >7 días
    ▼
data/fighters_complete.csv (base de datos viva, la API escribe en runtime)
```

## Quickstart

```bash
# dependencias (venv en la raíz)
venv/bin/pip install -r api/requirements.txt

# servicios
redis-server                          # obligatorio
ollama serve && ollama pull qwen2.5:7b   # opcional (fallback LLM)

# datos de desarrollo (solo si faltan modelo o CSV)
venv/bin/python scripts/setup_dev_data.py

# API
cd api && ../venv/bin/python main.py     # :8000, docs en /docs

# frontend
python3 -m http.server 3000 --directory frontend
```

Configuración LLM en `api/.env` (gitignored): `OPENAI_API_KEY`, `OPENAI_MODEL`, `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT`. Sin API key, opera en modo solo-Ollama.

## Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /` | Health check (modelo cargado, conteo de peleadores) |
| `POST /predict` | Predicción con probabilidades, factores clave y análisis LLM opcional |
| `GET /fighter/{name}` | Estadísticas de un peleador (CSV + auto-scraping) |
| `GET /search/fighters/{query}` | Búsqueda fuzzy de peleadores |
| `GET /health/llm` | Estado de proveedores LLM y circuit breakers |

## Tests

```bash
venv/bin/python -m pytest tests/ -v   # 15 tests del cliente LLM
python test_scraping.py               # prueba manual del scraper (red real)
```

## Documentación

- **`CLAUDE.md`** — fuente única de verdad del proyecto: estado real del código, qué es funcional y qué es placeholder, contratos frágiles y cómo trabajar en el repo. **Léelo antes de tocar código.**
- `README_LLM.md` — detalle del sistema LLM (fallback, circuit breakers, costos).
- `tasks/todo.md` — plan del refactor 2026-07 y su estado.
