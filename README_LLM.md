# Sistema LLM con Fallback - Guía de Uso Local

## 📋 Descripción

Sistema LLM para uso personal que usa:

1. **Proveedor primario**: OpenAI gpt-6-luna con `reasoning_effort="none"` (API de OpenAI)
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
│ OpenAI API  │       │  Ollama Local    │
│             │       │                  │
│ gpt-6-luna  │ (1°)  │  Qwen2.5:7b      │ (Fallback)
│             │       │                  │
│ • Calidad   │       │  • Sin costo API │
│   buena     │       │  • Offline       │
│ • ~$0.00043 │       │  • Privado       │
│ por análisis│       │                  │
└─────────────┘       └──────────────────┘
```

## ⚙️ Setup Local (Uso Personal)

### 1. Instalar dependencias Python

```bash
cd api
pip install -r requirements.txt
```

### 2. Configurar API Key de OpenAI

Obtén tu key en https://platform.openai.com/api-keys y ponla en `api/.env`:

```bash
OPENAI_API_KEY=sk-proj-...          # Tu key de OpenAI
OPENAI_MODEL=gpt-6-luna             # El cliente envía reasoning_effort="none"
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### 3. Verificar Ollama (opcional, es el fallback)

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

**Terminal 2 - Ollama (opcional):**
```bash
ollama serve
```

**Terminal 3 - API:**

```bash
cd api
python main.py
```

Verás:
```
INFO: Models and data loaded successfully
INFO: OpenAI client initialized with model gpt-6-luna
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
    "openai": {"available": true, "circuit_breaker": "closed"},
    "ollama": {"available": true, "reachable": true}
  }
}
```

### 6. (Opcional) Ejecutar tests

```bash
# Desde la raíz del proyecto
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
LLM_TIMEOUT=180            # Aplica SOLO a Ollama (OpenAI fijo en 30s)
```

### Customizar modelos

```bash
# Modelo predeterminado; parámetros y costos vigentes en CLAUDE.md → Componente 2
OPENAI_MODEL=gpt-6-luna       # reasoning_effort="none" se envía explícitamente

# Override compatible con el modelo anterior (sin parámetro reasoning_effort)
# OPENAI_MODEL=gpt-4o-mini

# Usar otro modelo de Ollama
OLLAMA_MODEL=llama3.1:8b
```

### Circuit Breaker personalizado

```python
from llm_client import LLMClient, CircuitBreaker

# Crear cliente con configuración custom
llm = LLMClient(
    openai_api_key="sk-proj-...",
    max_retries=5,
    timeout_seconds=45
)

# Ajustar thresholds del circuit breaker
llm.openai_breaker = CircuitBreaker(
    failure_threshold=10,  # Default: 5
    timeout=120            # Default: 60 segundos
)
```

## 📊 Monitoreo y Métricas

### Logs detallados

El sistema registra proveedor, modelo y latencia. Ejemplos de formato (latencias ilustrativas):

```
INFO: LLM analysis generated using openai (gpt-6-luna) in 12510ms (fallback: False)
```

```
WARNING: OpenAI RateLimitError on attempt 1, falling back to Ollama
INFO: LLM analysis generated using ollama (qwen2.5:7b) in 4560ms (fallback: True)
```

### Health check endpoint

```bash
# Monitoreo continuo
watch -n 5 'curl -s http://localhost:8000/health/llm | jq'
```

### Métricas importantes

1. **Latencia promedio**:
   - OpenAI: medir `latency_ms` en los logs del modelo configurado; timeout de 30 segundos por request
   - Ollama: depende del hardware local

2. **Tasa de fallback**:
   - Óptimo: <5% (la mayoría usa OpenAI)
   - Advertencia: >20% (problemas con la API de OpenAI)
   - Crítico: >80% (verificar API key / cuota)

3. **Circuit breaker state**:
   - `closed`: Normal
   - `half_open`: Recuperándose de fallas
   - `open`: Proveedor temporalmente deshabilitado

## 🐛 Troubleshooting

### OpenAI no funciona

**Síntoma**: Todos los análisis usan Ollama (fallback)

**Diagnóstico**:
```bash
# Verificar API key directamente
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-6-luna",
    "reasoning_effort": "none",
    "max_completion_tokens": 10,
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

**Soluciones**:
1. Verificar `OPENAI_API_KEY` en `api/.env`
2. Revisar cuota/billing en https://platform.openai.com/settings/organization/billing
3. Verificar que la key no esté revocada
4. Revisar los logs de la API (busca "OpenAI" en la salida de `main.py`)

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

### Rate limit de OpenAI

**Síntoma**: Logs muestran `RateLimitError` frecuente

**Soluciones**:
1. Reducir frecuencia de requests
2. Aumentar tiempo de cache en Redis (default: 1 hora)
3. Revisar tu tier de rate limits en https://platform.openai.com/settings/organization/limits

### Circuit breaker abierto

**Síntoma**: Health check muestra `"circuit_breaker": "open"`

**Solución**:
```bash
# Esperar timeout (60s para OpenAI, 30s para Ollama)
# O reiniciar la API
```

## 📈 Optimizaciones para Uso Personal

### Costos de OpenAI (GPT-6 Luna)

Con 320 tokens de entrada + 800 de salida, sin caché ni razonamiento, la estimación es **$0.000432 por análisis** ($0.432 por cada 1,000). Tarifas, supuestos y compatibilidad actualizados en `CLAUDE.md` → "Componente 2".

1. **Usar Luna sin razonamiento** (default del proyecto):
```bash
# En .env
OPENAI_MODEL=gpt-6-luna
```

2. **Usar Ollama por defecto** (gratis, 100% local):
```bash
# En .env, comenta la API key para forzar Ollama
# OPENAI_API_KEY=...
```

### Mejorar velocidad

1. **Ollama con GPU** (si tienes NVIDIA):
```bash
nvidia-smi  # Verificar GPU
# Ollama detecta y usa GPU automáticamente
```

2. **Cache en Redis más largo**:
```bash
# Las predicciones se cachean 1 hora por defecto
# Puedes aumentar el TTL en api/main.py:
redis_client.setex(cache_key, 86400, ...)  # 24 horas
```

## 🧪 Tests (Opcional)

Si quieres verificar que todo funciona correctamente:

```bash
# Desde la raíz del proyecto

# Todos los tests (con mocks, no usa API real)
pytest tests/test_llm_client.py -v

# Tests específicos
pytest tests/test_llm_client.py::test_openai_success -v
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
    llm = LLMClient(openai_api_key="sk-proj-...")

    prompt = "Analiza Jon Jones vs Stipe Miocic en 2 párrafos"

    # OpenAI (proveedor por defecto)
    openai_response = await llm.generate(prompt=prompt)

    # Ollama
    ollama_response = await llm.generate(
        prompt=prompt,
        force_provider=LLMProvider.OLLAMA
    )

    print(f"OpenAI latency: {openai_response.latency_ms}ms")
    print(f"Ollama latency: {ollama_response.latency_ms}ms")
    print(f"\nCalidad OpenAI (subjetiva): ⭐⭐⭐⭐")
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
# .env
```

**Importante**: Si compartes el proyecto, NO compartas tu `.env` con la API key. Si una key se expone (chat, pantalla compartida, commit accidental), rótala en https://platform.openai.com/api-keys.

## 🚀 Inicio Rápido (Resumen)

```bash
# Terminal 1
redis-server

# Terminal 2 (opcional, fallback)
ollama serve

# Terminal 3
cd api
python main.py

# Terminal 4 (verificar)
curl http://localhost:8000/health/llm | jq
```

## 📞 Referencias

- **Documentación OpenAI**: https://platform.openai.com/docs
- **Documentación Ollama**: https://github.com/ollama/ollama

---

**Última actualización**: 2026-09-26 (migración a GPT-6 Luna con esfuerzo `none`)
**Versión**: 2.0.0 (Uso Personal)
