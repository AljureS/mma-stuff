# Sistema LLM con Fallback - Guía de Uso Local

## 📋 Descripción

Sistema LLM para uso personal que usa:

1. **Proveedor primario**: Claude Sonnet 4.5 (Anthropic API)
2. **Fallback automático**: Ollama con Qwen2.5:7b (local)

**Nota**: Esta guía está enfocada en **ejecución local** para uso personal.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────┐
│         FastAPI Application          │
│                                      │
│    generate_llm_analysis(...)        │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│          LLMClient                    │
│  (api/llm_client.py)                 │
│                                      │
│  • Retry logic (exponential backoff) │
│  • Circuit breaker                   │
│  • Health checks                     │
│  • Metrics logging                   │
└──────┬───────────────────────┬───────┘
       │                       │
       ▼                       ▼
┌─────────────┐       ┌──────────────────┐
│ Claude API  │       │  Ollama Local    │
│             │       │                  │
│ Sonnet 4.5  │ (1°)  │  Qwen2.5:7b      │ (Fallback)
│             │       │                  │
│ • Calidad   │       │  • Sin costo API │
│   superior  │       │  • Baja latencia │
│ • ~$0.01 por│       │  • Offline       │
│   análisis  │       │                  │
└─────────────┘       └──────────────────┘
```

## ⚙️ Setup Local (Uso Personal)

### 1. Instalar dependencias Python

```bash
cd /home/saidsimon2/mma-predictor/api
pip install -r requirements.txt
```

### 2. Configurar API Key de Anthropic

Tu archivo `.env` ya tiene tu API key configurada. Si necesitas cambiarla:

```bash
nano /home/saidsimon2/mma-predictor/api/.env
```

Verifica que tenga:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...  # Tu key actual
OLLAMA_URL=http://localhost:11434
CLAUDE_MODEL=claude-sonnet-4-5-20250514
OLLAMA_MODEL=qwen2.5:7b
```

### 3. Verificar Ollama (ya instalado)

Ya tienes Ollama y Qwen2.5:7b instalados. Solo verifica:

```bash
# Verificar que tienes el modelo
ollama list | grep qwen

# Debería mostrar: qwen2.5:7b
```

### 4. Iniciar servicios locales

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Ollama:**
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

### 5. Verificar que todo funciona

**Desde otra terminal:**

```bash
# Health check general
curl http://localhost:8000/

# Health check LLM
curl http://localhost:8000/health/llm | jq
```

**Deberías ver:**
```json
{
  "status": "healthy",
  "providers": {
    "claude": {"available": true, "circuit_breaker": "closed"},
    "ollama": {"available": true, "reachable": true}
  }
}
```

### 6. (Opcional) Ejecutar tests

```bash
cd /home/saidsimon2/mma-predictor
pytest tests/test_llm_client.py -v
```

## 🚀 Uso

### Desde la API (Python)

```python
from llm_client import get_llm_client

# Obtener cliente singleton
llm = get_llm_client()

# Generar análisis (fallback automático)
response = await llm.generate(
    prompt="Analiza la pelea entre Jon Jones y Stipe Miocic",
    system_prompt="Eres un analista experto en MMA",
    max_tokens=800,
    temperature=0.7
)

print(f"Proveedor usado: {response.provider.value}")
print(f"Modelo: {response.model}")
print(f"Latencia: {response.latency_ms}ms")
print(f"Fallback usado: {response.fallback_used}")
print(f"Contenido:\n{response.content}")
```

### Desde la API REST (cURL)

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "fighter_a": "Jon Jones",
    "fighter_b": "Stipe Miocic",
    "include_llm_analysis": true
  }' | jq '.llm_analysis'
```

### Forzar proveedor específico

```python
from llm_client import LLMProvider

# Forzar Ollama (útil para testing)
response = await llm.generate(
    prompt="Test",
    force_provider=LLMProvider.OLLAMA
)
```

## 🔧 Configuración Avanzada

### Ajustar reintentos y timeout

```python
# En api/.env
LLM_MAX_RETRIES=5          # Default: 3
LLM_TIMEOUT=60             # Default: 30 (segundos)
```

### Customizar modelos

```python
# Usar otro modelo de Claude
CLAUDE_MODEL=claude-3-5-haiku-20241022  # Más barato

# Usar otro modelo de Ollama
OLLAMA_MODEL=llama3.1:8b
```

### Circuit Breaker personalizado

```python
from llm_client import LLMClient, CircuitBreaker

# Crear cliente con configuración custom
llm = LLMClient(
    anthropic_api_key="sk-ant-...",
    max_retries=5,
    timeout_seconds=45
)

# Ajustar thresholds del circuit breaker
llm.claude_breaker = CircuitBreaker(
    failure_threshold=10,  # Default: 5
    timeout=120            # Default: 60 segundos
)
```

## 📊 Monitoreo y Métricas

### Logs detallados

El sistema registra automáticamente:

```
INFO: LLM analysis generated using claude (claude-sonnet-4-5-20250514) in 1234ms (fallback: False)
```

```
WARNING: Claude RateLimitError on attempt 1, falling back to Ollama
INFO: LLM analysis generated using ollama (qwen2.5:7b) in 456ms (fallback: True)
```

### Health check endpoint

```bash
# Monitoreo continuo
watch -n 5 'curl -s http://localhost:8000/health/llm | jq'
```

### Métricas importantes

1. **Latencia promedio**:
   - Claude: 1-2 segundos
   - Ollama: 0.3-0.8 segundos

2. **Tasa de fallback**:
   - Óptimo: <5% (la mayoría usa Claude)
   - Advertencia: >20% (problemas con Claude API)
   - Crítico: >80% (verificar API key / cuota)

3. **Circuit breaker state**:
   - `closed`: Normal
   - `half_open`: Recuperándose de fallas
   - `open`: Proveedor temporalmente deshabilitado

## 🐛 Troubleshooting

### Claude no funciona

**Síntoma**: Todos los análisis usan Ollama (fallback)

**Diagnóstico**:
```bash
# Verificar API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

**Soluciones**:
1. Verificar `ANTHROPIC_API_KEY` en `.env`
2. Revisar cuota en https://console.anthropic.com/settings/billing
3. Verificar que la key no esté expirada
4. Revisar logs: `tail -f api/logs/app.log | grep -i anthropic`

### Ollama no responde

**Síntoma**: Error "Análisis LLM no disponible temporalmente"

**Diagnóstico**:
```bash
# Verificar servicio Ollama
curl http://localhost:11434/api/tags

# Verificar modelo descargado
ollama list | grep qwen
```

**Soluciones**:
1. Iniciar servidor: `ollama serve`
2. Descargar modelo: `ollama pull qwen2.5:7b`
3. Cambiar `OLLAMA_URL` si Ollama está en otro puerto
4. Verificar logs: `journalctl -u ollama -f` (Linux)

### Rate limit de Claude

**Síntoma**: Logs muestran `RateLimitError` frecuente

**Soluciones**:
1. Reducir frecuencia de requests
2. Aumentar tiempo de cache en Redis (default: 1 hora)
3. Usar modelo más barato: `claude-3-5-haiku-20241022`
4. Aumentar cuota en Anthropic Console

### Circuit breaker abierto

**Síntoma**: Health check muestra `"circuit_breaker": "open"`

**Solución**:
```bash
# Esperar timeout (60s para Claude, 30s para Ollama)
# O reiniciar API
systemctl restart mma-api
```

## 📈 Optimizaciones para Uso Personal

### Reducir costos de Claude (~$1-3/mes actual)

1. **Usar Haiku si haces muchos análisis**:
```bash
# En .env
CLAUDE_MODEL=claude-3-5-haiku-20241022  # ~10x más barato
```

2. **Usar Ollama por defecto** (gratis):
```bash
# En .env, comenta la API key para forzar Ollama
# ANTHROPIC_API_KEY=...
```

### Mejorar velocidad

1. **Ollama con GPU** (si tienes NVIDIA):
```bash
nvidia-smi  # Verificar GPU
# Ollama detecta y usa GPU automáticamente
```

2. **Cache en Redis más largo**:
```bash
# Análisis se cachean 1 hora por defecto
# Puedes aumentar en api/main.py línea 160:
redis_client.setex(cache_key, 86400, ...)  # 24 horas
```

## 🧪 Tests (Opcional)

Si quieres verificar que todo funciona correctamente:

```bash
cd /home/saidsimon2/mma-predictor

# Todos los tests (con mocks, no usa API real)
pytest tests/test_llm_client.py -v

# Tests específicos
pytest tests/test_llm_client.py::test_claude_success -v
pytest tests/test_llm_client.py::test_ollama_success -v
```

## 📚 Ejemplos Completos

### Ejemplo 1: Análisis básico con logging

```python
import asyncio
import logging
from llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)

async def analyze_fight():
    llm = get_llm_client()

    response = await llm.generate(
        prompt="""Analiza: Jon Jones vs Stipe Miocic

        Jon Jones: 27-1-0, Alcance 215cm, 37 años
        Stipe Miocic: 20-4-0, Alcance 203cm, 42 años

        Predicción ML: 73% Jon Jones
        """,
        system_prompt="Eres un analista experto de MMA",
        max_tokens=600,
        temperature=0.7
    )

    print(f"\n{'='*60}")
    print(f"Proveedor: {response.provider.value}")
    print(f"Modelo: {response.model}")
    print(f"Latencia: {response.latency_ms}ms")
    print(f"Tokens: {response.tokens_used}")
    print(f"Fallback: {response.fallback_used}")
    print(f"{'='*60}\n")
    print(response.content)

asyncio.run(analyze_fight())
```

### Ejemplo 2: Comparación de proveedores

```python
import asyncio
from llm_client import LLMClient, LLMProvider

async def compare_providers():
    llm = LLMClient(anthropic_api_key="sk-ant-...")

    prompt = "Analiza Jon Jones vs Stipe Miocic en 2 párrafos"

    # Claude
    claude_response = await llm.generate(
        prompt=prompt,
        force_provider=LLMProvider.CLAUDE
    )

    # Ollama
    ollama_response = await llm.generate(
        prompt=prompt,
        force_provider=LLMProvider.OLLAMA
    )

    print(f"Claude latency: {claude_response.latency_ms}ms")
    print(f"Ollama latency: {ollama_response.latency_ms}ms")
    print(f"\nCalidad Claude (subjetiva): ⭐⭐⭐⭐⭐")
    print(f"Calidad Ollama (subjetiva): ⭐⭐⭐")

asyncio.run(compare_providers())
```

### Ejemplo 3: Manejo robusto de errores

```python
import asyncio
from llm_client import get_llm_client, LLMProvider

async def robust_analysis(fighter_a, fighter_b):
    llm = get_llm_client()

    try:
        response = await llm.generate(
            prompt=f"Analiza {fighter_a} vs {fighter_b}",
            max_tokens=500,
            temperature=0.7
        )

        if response.error:
            print(f"⚠️ Advertencia: {response.error}")
            print(f"Usando mensaje genérico")
            return response.content  # Mensaje de error amigable

        if response.fallback_used:
            print(f"ℹ️ Usando fallback: {response.provider.value}")

        return response.content

    except Exception as e:
        print(f"❌ Error crítico: {e}")
        return "Análisis temporalmente no disponible."

asyncio.run(robust_analysis("Jon Jones", "Stipe Miocic"))
```

## 🔐 Seguridad (Uso Personal)

### Proteger tu API Key

Tu `.env` ya está en `.gitignore`, pero por si acaso:

```bash
# Verificar que .env NO se suba a git
cat .gitignore | grep .env

# Debería mostrar:
# api/.env
# .env
```

**Importante**: Si compartes el proyecto, NO compartas tu `.env` con la API key.

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

## 📞 Referencias

- **Documentación Anthropic**: https://docs.anthropic.com/
- **Documentación Ollama**: https://github.com/ollama/ollama

---

**Última actualización**: 2025-10-06
**Versión**: 1.0.0 (Uso Personal)
