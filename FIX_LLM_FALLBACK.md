# 🔧 Fix del Sistema de Fallback LLM - Instrucciones Completas

## 📋 Resumen del Problema

**Síntoma:** Las predicciones retornaban `"Lo siento, el análisis LLM no está disponible temporalmente."` aunque Ollama estaba funcionando perfectamente.

**Causa Raíz:** El timeout HTTP para Ollama era de **30 segundos**, pero generar análisis con Qwen2.5:7b toma **~60-120 segundos**. El cliente cortaba la conexión antes de que Ollama terminara.

**Solución:** Incrementar el timeout de Ollama a **180 segundos** (3 minutos) manteniendo el timeout de Claude en 30s.

---

## ✅ Cambios Implementados

### 1. **Modificación en `api/.env`**
```bash
# ANTES
LLM_TIMEOUT=30

# DESPUÉS
LLM_TIMEOUT=180  # 3 minutos para Ollama (modelos locales necesitan más tiempo)
```

### 2. **Modificaciones en `api/llm_client.py`**

#### a) Constructor con timeout diferenciado
- Agregado parámetro `ollama_timeout_seconds` para separar timeouts
- Claude: 30s (API remota rápida)
- Ollama: 180s (modelo local más lento)

#### b) Método `_generate_ollama()`
- Cambiado de `self.timeout_seconds` a `self.ollama_timeout_seconds`

#### c) Función `get_llm_client()`
- Configuración explícita: Claude=30s, Ollama=180s (desde `LLM_TIMEOUT`)

#### d) Logging mejorado
- Muestra timeout de Ollama en warning inicial
- Reporta tamaño de respuesta en caracteres

---

## 🚀 PASOS PARA ACTIVAR LA SOLUCIÓN

### ⚠️ IMPORTANTE: El servidor FastAPI DEBE reiniciarse

El servidor con `--reload` solo recarga código, pero las variables de entorno (`.env`) requieren reinicio completo.

### **Opción 1: Reinicio Manual (RECOMENDADO)**

```bash
# 1. En la terminal donde corre el servidor, presionar Ctrl+C para detenerlo

# 2. Limpiar cache de Redis para forzar nuevas predicciones
redis-cli FLUSHALL

# 3. Reiniciar el servidor
cd ~/mma-stuff/api
source ../venv/bin/activate
python main.py
```

### **Opción 2: Reinicio desde Otra Terminal**

```bash
# 1. Matar proceso del servidor
pkill -f "uvicorn main:app" -SIGTERM

# 2. Esperar que termine
sleep 2

# 3. Limpiar cache de Redis
redis-cli FLUSHALL

# 4. Reiniciar servidor
cd ~/mma-stuff/api
source ../venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 VERIFICACIÓN DE LA SOLUCIÓN

### **Test 1: Verificar LLM Client Directamente**

Este test confirma que el LLM client funciona sin pasar por la API:

```bash
cd ~/mma-stuff
source venv/bin/activate
python3 test_llm_direct.py
```

**Resultado Esperado:**
```
✓ LLM Client initialized:
  - Claude available: False
  - Ollama URL: http://localhost:11434
  - Ollama model: qwen2.5:7b
  - Ollama timeout: 180s          ← ✅ DEBE SER 180s
  - Claude timeout: 30s

🚀 Generating text with Ollama (this may take ~2 minutes)...

✅ SUCCESS!
  - Provider: ollama
  - Model: qwen2.5:7b
  - Latency: ~60000ms (60s)
  - Content length: 1200-1500 chars  ← ✅ ANÁLISIS GENERADO
```

**Si falla:** Verificar que Ollama esté corriendo (`ollama serve`) y el modelo instalado (`ollama list`).

---

### **Test 2: Health Check del Sistema LLM**

```bash
curl -s http://localhost:8000/health/llm | python3 -m json.tool
```

**Resultado Esperado:**
```json
{
  "status": "healthy",
  "providers": {
    "claude": {
      "available": false,
      "circuit_breaker": "closed",
      "failures": 0
    },
    "ollama": {
      "available": true,
      "circuit_breaker": "closed",
      "failures": 0,
      "reachable": true        ← ✅ DEBE SER true
    }
  },
  "timestamp": "..."
}
```

---

### **Test 3: Predicción Completa con Análisis LLM (CRÍTICO)**

Este es el test definitivo que confirma que el sistema funciona end-to-end:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "fighter_a": "Azamat Bekoev",
    "fighter_b": "Yousri Belgaroui",
    "include_llm_analysis": true
  }' | python3 -m json.tool > prediction_result.json

# Ver solo el análisis LLM
cat prediction_result.json | python3 -c "import sys, json; d=json.load(sys.stdin); print('LLM Analysis:', d['llm_analysis'][:500])"
```

**Resultado Esperado:**

✅ **Campo `llm_analysis` contiene texto generado**, ejemplo:
```
"llm_analysis": "Basándonos en las estadísticas proporcionadas, se puede inferir que la pelea entre Azamat Bekoev y Yousri Belgaroui será bastante desigual. Bekoev, con un alcance más corto pero una experiencia superior..."
```

❌ **NO debe contener:**
```
"llm_analysis": "Lo siento, el análisis LLM no está disponible temporalmente."
```

**Nota:** Esta predicción toma **~60-120 segundos** porque Ollama genera el análisis. Es normal.

---

### **Test 4: Verificar en el Frontend**

```bash
# 1. Abrir navegador en: http://localhost:8080

# 2. Hacer una predicción:
#    - Fighter A: Azamat Bekoev
#    - Fighter B: Yousri Belgaroui
#    - Marcar "Incluir análisis LLM"
#    - Clic en "Predecir Resultado"

# 3. Esperar ~2 minutos

# 4. Verificar que la sección "Análisis IA" muestre texto generado
```

**Resultado Esperado:**
- Barra de progreso mientras genera (1-2 minutos)
- Sección "Análisis IA" con 2-3 párrafos de análisis técnico
- NO debe mostrar mensaje de error

---

## 📊 Métricas de Rendimiento Esperadas

| Métrica | Valor |
|---------|-------|
| **Primera predicción (sin cache)** | 60-120 segundos |
| **Predicciones subsecuentes (con cache)** | ~5 milisegundos |
| **Tamaño típico de análisis** | 800-1500 caracteres |
| **Timeout Ollama** | 180 segundos |
| **Timeout Claude** | 30 segundos |

---

## 🐛 Troubleshooting

### **Problema 1: Todavía aparece el mensaje de error**

**Causa:** El servidor no se reinició o Redis tiene cache viejo.

**Solución:**
```bash
# Limpiar cache completamente
redis-cli FLUSHALL

# Reiniciar servidor (Ctrl+C en la terminal del servidor, luego)
cd ~/mma-stuff/api
source ../venv/bin/activate
python main.py
```

---

### **Problema 2: "Connection refused" a Ollama**

**Causa:** Ollama no está corriendo.

**Solución:**
```bash
# Verificar si Ollama está corriendo
ps aux | grep ollama

# Si no está, iniciar Ollama
ollama serve

# En otra terminal, verificar que el modelo esté instalado
ollama list | grep qwen2.5
```

---

### **Problema 3: Timeout después de 180s**

**Causa:** El análisis requiere más tiempo (modelo muy lento o hardware limitado).

**Solución:** Incrementar timeout en `api/.env`:
```bash
LLM_TIMEOUT=300  # 5 minutos
```

Luego reiniciar servidor.

---

### **Problema 4: `test_llm_direct.py` muestra timeout 30s**

**Causa:** El archivo `.env` no se cargó correctamente.

**Solución:**
```bash
# Verificar que .env existe y tiene el cambio
cat api/.env | grep LLM_TIMEOUT

# Debe mostrar:
# LLM_TIMEOUT=180

# Si muestra 30, editar manualmente:
nano api/.env
# Cambiar LLM_TIMEOUT=30 a LLM_TIMEOUT=180
```

---

## 📝 Logs del Servidor

### **Logs Correctos (Sistema Funcionando)**

Al iniciar el servidor, debes ver:
```
INFO: No ANTHROPIC_API_KEY found - Claude disabled, using Ollama only (qwen2.5:7b at http://localhost:11434, timeout: 180s)
INFO: Models and data loaded successfully
```

Durante una predicción:
```
INFO: Generated prediction for Azamat Bekoev vs Yousri Belgaroui
INFO: Ollama (qwen2.5:7b) response generated in 58564ms (1283 chars)
```

### **Logs con Problemas**

Si ves esto, el sistema NO está funcionando:
```
ERROR: Ollama also failed: timeout
ERROR: Error generating LLM analysis: ...
```

---

## 🔮 Prevención de Problemas Futuros

### **1. Agregar Variable de Entorno Separada (Opcional)**

Para mayor claridad:

**En `api/.env`:**
```bash
CLAUDE_TIMEOUT=30
OLLAMA_TIMEOUT=180
```

**En `api/llm_client.py` función `get_llm_client()`:**
```python
timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT", "30")),
ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT", "180"))
```

---

### **2. Agregar Test Automatizado**

**En `tests/test_llm_client.py`:**
```python
@pytest.mark.asyncio
async def test_ollama_timeout_sufficient():
    """Verificar que el timeout de Ollama sea >= 120s"""
    client = get_llm_client()
    assert client.ollama_timeout_seconds >= 120, \
        f"Ollama timeout muy bajo: {client.ollama_timeout_seconds}s (mínimo: 120s)"
```

---

### **3. Monitoreo de Latencia**

**En `api/llm_client.py` método `_generate_ollama()`:**
```python
if latency_ms > 150000:  # 150 segundos
    logger.warning(
        f"Ollama response took {latency_ms/1000:.1f}s "
        f"(close to {self.ollama_timeout_seconds}s timeout limit)"
    )
```

---

## 📚 Archivos Modificados

```
api/.env                    → LLM_TIMEOUT=180
api/llm_client.py          → Timeout diferenciado + mejor logging
test_llm_direct.py         → Script de prueba (NUEVO)
FIX_LLM_FALLBACK.md        → Este archivo (NUEVO)
```

---

## ✅ Checklist Final

Antes de considerar el problema resuelto, verifica:

- [ ] `cat api/.env | grep LLM_TIMEOUT` muestra `180`
- [ ] Servidor FastAPI reiniciado completamente
- [ ] `redis-cli FLUSHALL` ejecutado
- [ ] `python3 test_llm_direct.py` muestra `Ollama timeout: 180s`
- [ ] Test directo genera análisis exitosamente
- [ ] `curl http://localhost:8000/health/llm` muestra Ollama reachable
- [ ] Predicción desde API retorna análisis (no mensaje de error)
- [ ] Frontend muestra análisis en sección "Análisis IA"

---

## 🎯 Resumen Ejecutivo

| Aspecto | Estado |
|---------|--------|
| **Problema identificado** | ✅ Timeout insuficiente (30s → 180s) |
| **Root cause** | ✅ `api/llm_client.py:308` |
| **Solución implementada** | ✅ Timeout diferenciado por proveedor |
| **Test directo** | ✅ Funciona (58s, 1283 chars) |
| **Acción requerida** | ⚠️ **Reiniciar servidor FastAPI** |

---

## 🆘 Contacto

Si después de seguir estos pasos el problema persiste:

1. **Verificar logs del servidor:** Buscar mensajes de error específicos
2. **Ejecutar todos los tests:** Los 4 tests de verificación
3. **Revisar estado de servicios:** Ollama, Redis, FastAPI
4. **Documentar error:** Guardar logs completos y outputs de tests

---

**Última actualización:** 2025-10-15
**Versión del fix:** 1.0
**Probado en:** Ubuntu WSL2, Python 3.x, Ollama 0.x, Qwen2.5:7b
