# MMA Fight Predictor - Sistema de Predicción con ML + IA

Sistema completo de predicción de peleas MMA que combina Machine Learning (XGBoost) con análisis cualitativo mediante LLM(claude | local con qwen ). El modelo utiliza 16 features técnicas para calcular probabilidades de victoria, mientras que un sistema de IA dual (Claude API con fallback a Ollama local) genera análisis explicativos detallados. La arquitectura incluye cache inteligente con Redis, scraping automático de datos, y una interfaz web moderna para visualización de predicciones en tiempo real.

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USUARIO / NAVEGADOR                         │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Frontend (HTML/CSS/JavaScript)                   │  │
│  │            frontend/index.html (puerto 3000)                  │  │
│  │  • Input de peleadores                                        │  │
│  │  • Gráficos de probabilidades (Chart.js)                      │  │
│  │  • Visualización de análisis IA                               │  │
│  └─────────────────────┬─────────────────────────────────────────┘  │
└────────────────────────┼────────────────────────────────────────────┘
                         │ HTTP POST /predict
                         │ (include_llm_analysis: true/false)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BACKEND - FastAPI                             │
│                   api/main.py (puerto 8000)                         │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  1. Validar peleadores en DB                                │    │
│  │  2. Cargar datos completos (fighters_complete.csv)          │    │
│  │  3. Calcular 16 features del modelo                         │    │
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                            │
│                        ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │         PREDICCIÓN ML (XGBoost)                             │    │
│  │         models/mma_prediction_model.pkl                     │    │
│  │  • Input: 16 features (diferencias físicas, técnicas, etc.) │    │
│  │  • Output: Probabilidades (ej: 80.5% vs 19.5%)              │    │
│  │  • ⚠️ AQUÍ SE DEFINEN LOS %                                 |    |
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                            │
│                        ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  4. Generar análisis LLM (si include_llm_analysis=true)     │    │ 
│  │     → Llama a llm_client.generate()                         │    │
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                            │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM CLIENT (Orquestador)                         │
│                     api/llm_client.py                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  async def generate():                                      │    │
│  │    1. ¿Claude disponible? → Intentar Claude API             │    │
│  │    2. Si falla/timeout → Fallback automático a Ollama       │    │
│  │    3. Reintentos exponenciales (1s, 2s, 4s)                 │    │
│  │    4. Circuit breaker para proteger servicios               │    │
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                            │
│          ┌─────────────┴─────────────┐                              │
│          │                           │                              │
│          ▼                           ▼                              │
│  ┌───────────────┐          ┌────────────────────┐                  │
│  │ Claude API    │          │ Ollama Local       │                  │
│  │ (Primario)    │  FALLA   │ (Fallback)         │                  │
│  │               │  ───→    │                    │                  │
│  │ Sonnet 4.5    │          │ Qwen2.5:7b         │                  │
│  │ Timeout: 30s  │          │ Timeout: 180s      │                  │
│  │ Externo/Rápido│          │ Local/Lento        │                  │
│  └───────────────┘          └────────────────────┘                  │
│                                                                     │
│  📝 LLM genera análisis cualitativo DESPUÉS de la predicción        │
│  ⚠️ NO modifica los % - solo explica el resultado del modelo ML     │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         │ Análisis generado (1200-1500 chars)
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                 ALMACENAMIENTO Y DATOS                             │
│                                                                    │
│  ┌──────────────────────┐     ┌──────────────────────────────┐     │
│  │  PostgreSQL          │     │  Redis Cache                 │     │
│  │  Base de datos       │     │  Cache de predicciones       │     │
│  │  principal           │     │  • TTL: 1 hora (3600s)       │     │
│  │  (Opcional)          │     │  • Key: prediction:{A}:{B}   │     │
│  └──────────────────────┘     │  • Evita recálculos          │     │
│                               └──────────────────────────────┘     │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Archivos CSV                                                │  │
│  │  data/fighters_complete.csv  - Base de datos de peleadores   │  │
│  │  data/fight_history.csv      - Historial de peleas           │  │
│  │  data/training_data.csv      - Datos para entrenar modelo    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Web Scraping (Actualización de Datos)                       │  │
│  │  scripts/data_collection.py                                  │  │
│  │  • UFCStats.com - Estadísticas oficiales                     │  │
│  │  • Sherdog - Rankings y datos históricos                     │  │
│  │  • Tapology - Eventos futuros                                │  │
│  │  • Auto-scraping si datos > 7 días de antigüedad             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Componentes de la Arquitectura

1. **Frontend (mma_frontend.html)** - Interfaz web con búsqueda de peleadores, gráficos interactivos y visualización de predicciones en tiempo real
2. **API FastAPI (api/main.py)** - Servidor backend que orquesta validación, cálculo de features, predicción ML y generación de análisis LLM
3. **Modelo XGBoost (mma_prediction_model.pkl)** - Clasificador binario que procesa 16 features y genera probabilidades de victoria (único componente que afecta los %)
4. **LLM Client (api/llm_client.py)** - Orquestador que intenta Claude API primero y hace fallback automático a Ollama si falla
5. **Claude API (Anthropic)** - Servicio externo de IA para análisis rápido (30s timeout), usado como proveedor primario
6. **Ollama Local (Qwen2.5:7b)** - Modelo LLM local como fallback, más lento (180s timeout) pero siempre disponible
7. **Redis Cache** - Almacenamiento en memoria para cachear predicciones por 1 hora y evitar recálculos innecesarios
8. **PostgreSQL (Opcional)** - Base de datos relacional para almacenamiento persistente de peleas y resultados históricos
9. **CSV Data Store (data/)** - Archivos planos con datos de peleadores, historial de peleas y datos de entrenamiento del modelo
10. **Web Scraper (data_collection.py)** - Sistema automatizado que recopila datos frescos de UFCStats, Sherdog y Tapology cuando los datos tienen >7 días


# ============================================
# INICIAR MMA PREDICTOR - COPIAR Y PEGAR TODO
# ============================================

# Terminal 1 - Backend API
cd ~/mma-stuff/api
source venv/bin/activate
python main.py

# ============================================
# ABRIR NUEVA TERMINAL PARA ESTO:
# ============================================

# Terminal 2 - Frontend
cd ~/mma-stuff
python3 -m http.server 3000

# ============================================
# ABRIR EN NAVEGADOR:
# http://localhost:3000
# http://localhost:8000/docs
# ============================================

# ============================================
# VERIFICAR (opcional - en Terminal 3)
# ============================================
curl http://localhost:8000/
curl http://localhost:3000/

# ============================================
# PARAR TODO: Ctrl+C en cada terminal
# ============================================