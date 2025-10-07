# Guía de Ejecución Local - MMA Fight Predictor

> **Nota**: Esta guía está enfocada en **ejecución local para uso personal**, no en deployment a producción.

## 📦 Setup Local

### 1. Instalar dependencias Python

```bash
cd /home/saidsimon2/mma-predictor/api
pip install -r requirements.txt
```

### 2. Verificar configuración

Tu `.env` ya está configurado con tu API key. Verifica que esté correcto:

```bash
cat /home/saidsimon2/mma-predictor/api/.env | grep ANTHROPIC_API_KEY
```

### 3. Iniciar servicios en terminales separadas

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Ollama (ya tienes qwen2.5:7b descargado):**
```bash
ollama serve
```

**Terminal 3 - API:**

```bash
cd /home/saidsimon2/mma-predictor/api
python main.py
```

Verás:
```
INFO: Models and data loaded successfully
INFO: Claude client initialized with model claude-sonnet-4-5-20250514
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 4. Verificar que funciona

**Terminal 4:**

```bash
# Health check
curl http://localhost:8000/health/llm | jq

# Predicción de prueba (si tienes datos)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "fighter_a": "Jon Jones",
    "fighter_b": "Stipe Miocic",
    "include_llm_analysis": true
  }' | jq '.llm_analysis'
```

## 🧪 Testing (Opcional)

### Tests unitarios

```bash
cd /home/saidsimon2/mma-predictor

# Todos los tests
pytest tests/test_llm_client.py -v

# Tests específicos
pytest tests/test_llm_client.py::test_claude_success -v
pytest tests/test_llm_client.py::test_ollama_success -v
```

## 🔧 Troubleshooting Local

### Redis no inicia
```bash
# Verificar si ya está corriendo
ps aux | grep redis

# Matar proceso si es necesario
pkill redis-server

# Reiniciar
redis-server
```

### Ollama no responde
```bash
# Verificar servicio
ps aux | grep ollama

# Reiniciar
pkill ollama
ollama serve
```

### Claude siempre usa fallback
```bash
# Verificar API key
cat /home/saidsimon2/mma-predictor/api/.env | grep ANTHROPIC_API_KEY

# Test manual
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-5-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

## 🚀 Inicio Rápido (Resumen)

```bash
# Terminal 1
redis-server

# Terminal 2
ollama serve

# Terminal 3
cd /home/saidsimon2/mma-predictor/api
python main.py

# Terminal 4 (verificar)
curl http://localhost:8000/health/llm | jq
```

---

**Última actualización**: 2025-10-06
**Versión**: Uso Personal Local
