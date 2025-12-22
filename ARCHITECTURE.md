# MMA Fight Predictor - Arquitectura

Sistema de predicción de peleas MMA que usa Machine Learning (XGBoost con 16 features) para calcular probabilidades de victoria, y LLMs (Claude/Ollama) para generar análisis cualitativos. El usuario selecciona dos peleadores en el frontend, la API procesa sus estadísticas, el modelo ML predice el ganador, y opcionalmente un LLM explica el porqué.

---

## Flujo del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO                                        │
│                         (selecciona 2 peleadores)                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (mma_frontend.html)                        │
│                      TailwindCSS + Chart.js + JS ES6                        │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ POST /predict
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API (api/main.py)                                  │
│                              FastAPI                                        │
│                                                                             │
│   ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────┐   │
│   │    Redis    │◄───│   /predict       │───►│   ml_system.py          │   │
│   │   (cache)   │    │   /fighter       │    │   XGBoost + 16 features │   │
│   └─────────────┘    │   /search        │    └────────────┬────────────┘   │
│                      │   /events        │                 │                │
│                      └──────────────────┘                 ▼                │
│                                                  ┌─────────────────┐       │
│                                                  │  llm_client.py  │       │
│                                                  └────────┬────────┘       │
│                                                           │                │
│                                           ┌───────────────┼───────────────┐│
│                                           ▼               ▼               ││
│                                    ┌───────────┐   ┌─────────────┐        ││
│                                    │  Claude   │   │   Ollama    │        ││
│                                    │ Sonnet4.5 │   │ Qwen2.5:7b  │        ││
│                                    │   (1ro)   │   │ (fallback)  │        ││
│                                    └───────────┘   └─────────────┘        ││
│                                                                           ││
└───────────────────────────────────────────────────────────────────────────┘│
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATOS                                          │
│                                                                             │
│   ┌────────────────┐    ┌───────────────┐    ┌─────────────────────────┐   │
│   │   PostgreSQL   │    │  data/*.csv   │    │  models/*.pkl           │   │
│   │  (peleadores)  │    │  (histórico)  │    │  (modelo entrenado)     │   │
│   └────────────────┘    └───────────────┘    └─────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Mapa de Archivos

```
mma-stuff/
│
├── api/                          # BACKEND
│   ├── main.py                   # Servidor FastAPI - endpoints
│   ├── ml_system.py              # Motor ML - XGBoost + 16 features
│   ├── llm_client.py             # Cliente LLM - Claude → Ollama fallback
│   └── .env                      # Variables de entorno (API keys, config)
│
├── scripts/                      # UTILIDADES
│   ├── data_collection.py        # Scraping: UFCStats, Sherdog, Tapology
│   └── setup_dev_data.py         # Setup datos desarrollo
│
├── frontend/                     # FRONTEND
│   └── mma_frontend.html         # UI completa (HTML + CSS + JS)
│
├── data/                         # DATOS
│   ├── fighters_complete.csv     # Base peleadores
│   ├── fight_history.csv         # Historial peleas
│   └── training_data.csv         # Dataset entrenamiento
│
├── models/                       # MODELOS ML
│   └── mma_prediction_model.pkl  # Modelo XGBoost entrenado
│
├── tests/                        # TESTS
│   └── test_llm_client.py        # Tests LLM client
│
├── CLAUDE.md                     # Documentación completa (fuente de verdad)
└── ARCHITECTURE.md               # Este archivo
```

---

## Qué Modificar Según el Cambio

| Si quieres...                          | Modifica...                        |
|----------------------------------------|------------------------------------|
| Agregar endpoint API                   | `api/main.py`                      |
| Cambiar features del modelo            | `api/ml_system.py`                 |
| Cambiar modelo LLM o fallback          | `api/llm_client.py` + `.env`       |
| Modificar UI/diseño                    | `frontend/mma_frontend.html`       |
| Agregar fuente de datos                | `scripts/data_collection.py`       |
| Reentrenar modelo                      | `POST /retrain` o `ml_system.py`   |
| Cambiar config (keys, timeouts)        | `api/.env`                         |

---

## Stack Tecnológico

**Backend:** FastAPI + XGBoost + Anthropic SDK + aiohttp
**Frontend:** HTML5 + TailwindCSS + Chart.js
**DB:** PostgreSQL + Redis (cache)
**LLM:** Claude Sonnet 4.5 (primario) → Ollama Qwen2.5:7b (fallback)
