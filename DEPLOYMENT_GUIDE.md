# Guía de Deployment - MMA Fight Predictor

## 📦 Setup Rápido

### 1. Clonar e instalar

```bash
git clone <repo-url> mma-predictor
cd mma-predictor/api

# Crear virtualenv
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# O en Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
nano .env  # O tu editor preferido
```

**IMPORTANTE**: Configurar `ANTHROPIC_API_KEY` con tu API key de https://console.anthropic.com/

### 3. Iniciar servicios

#### Redis (cache)
```bash
# Linux/WSL
sudo apt install redis-server
redis-server

# macOS
brew install redis
redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

#### Ollama (fallback LLM) - Opcional pero recomendado
```bash
# Linux/WSL
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull qwen2.5:7b

# macOS
brew install ollama
ollama serve
ollama pull qwen2.5:7b

# Verificar
curl http://localhost:11434/api/tags
```

### 4. Ejecutar API

```bash
cd api
python main.py
```

Verás:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Models and data loaded successfully
INFO:     Claude client initialized with model claude-sonnet-4-5-20250514
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5. Verificar instalación

```bash
# Health check general
curl http://localhost:8000/ | jq

# Health check LLM
curl http://localhost:8000/health/llm | jq

# Test prediction (requiere datos de peleadores en DB)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "fighter_a": "Jon Jones",
    "fighter_b": "Stipe Miocic",
    "include_llm_analysis": true
  }' | jq
```

## 🧪 Testing

### Tests unitarios (con mocks)

```bash
# Todos los tests
pytest tests/test_llm_client.py -v

# Tests específicos
pytest tests/test_llm_client.py::test_claude_success -v
pytest tests/test_llm_client.py::test_claude_rate_limit_fallback_to_ollama -v
pytest tests/test_llm_client.py::test_circuit_breaker_opens_after_threshold -v

# Con cobertura
pytest tests/test_llm_client.py --cov=api.llm_client --cov-report=term-missing

# Generar reporte HTML
pytest tests/test_llm_client.py --cov=api.llm_client --cov-report=html
open htmlcov/index.html
```

### Tests de integración (requiere servicios reales)

```bash
# Requiere: ANTHROPIC_API_KEY válida + Ollama running
export ANTHROPIC_API_KEY=sk-ant-...
ollama serve  # En otra terminal

# Ejecutar tests de integración
pytest tests/ -v --integration

# Test manual de Claude
python -c "
import asyncio
from api.llm_client import get_llm_client

async def test():
    llm = get_llm_client()
    response = await llm.generate('Test Claude API')
    print(f'Provider: {response.provider.value}')
    print(f'Content: {response.content}')

asyncio.run(test())
"

# Test manual de Ollama
curl -X POST http://localhost:11434/api/generate \
  -d '{
    "model": "qwen2.5:7b",
    "prompt": "Test Ollama",
    "stream": false
  }' | jq '.response'
```

### Performance testing

```bash
# Instalar herramienta de benchmarking
pip install locust

# Crear archivo locustfile.py
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between

class MMAUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def predict_fight(self):
        self.client.post("/predict", json={
            "fighter_a": "Jon Jones",
            "fighter_b": "Stipe Miocic",
            "include_llm_analysis": True
        })

    @task(2)
    def health_check(self):
        self.client.get("/health/llm")
EOF

# Ejecutar test de carga
locust -f locustfile.py --host=http://localhost:8000

# Abrir UI en: http://localhost:8089
```

## 🚀 Production Deployment

### Option 1: Docker

```bash
# Crear Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    redis-server \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copiar requirements
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY api/ ./api/
COPY data/ ./data/
COPY models/ ./models/

# Exponer puerto
EXPOSE 8000

# Script de inicio
CMD ["sh", "-c", "redis-server --daemonize yes && ollama serve & sleep 5 && ollama pull qwen2.5:7b && cd api && python main.py"]
EOF

# Build
docker build -t mma-predictor .

# Run
docker run -d \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  --name mma-api \
  mma-predictor

# Verificar logs
docker logs -f mma-api
```

### Option 2: Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: serve

  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - ollama
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
      - OLLAMA_URL=http://ollama:11434
    volumes:
      - ./data:/app/data
      - ./models:/app/models

volumes:
  redis_data:
  ollama_data:
```

```bash
# Iniciar stack completo
docker-compose up -d

# Ver logs
docker-compose logs -f api

# Detener
docker-compose down
```

### Option 3: Systemd Service (Linux)

```bash
# Crear servicio
sudo nano /etc/systemd/system/mma-api.service
```

```ini
[Unit]
Description=MMA Fight Predictor API
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mma-predictor/api
Environment="PATH=/opt/mma-predictor/api/venv/bin"
EnvironmentFile=/opt/mma-predictor/api/.env
ExecStart=/opt/mma-predictor/api/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar y iniciar
sudo systemctl enable mma-api
sudo systemctl start mma-api

# Status
sudo systemctl status mma-api

# Logs
journalctl -u mma-api -f
```

### Option 4: Heroku

```bash
# Crear Procfile
echo "web: cd api && uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile

# Crear runtime.txt
echo "python-3.10.12" > runtime.txt

# Deploy
heroku create mma-fight-predictor
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
git push heroku main

# Ver logs
heroku logs --tail

# Escalar
heroku ps:scale web=2
```

### Option 5: AWS EC2

```bash
# Conectar a instancia
ssh -i key.pem ubuntu@ec2-xxx.amazonaws.com

# Instalar dependencias
sudo apt update
sudo apt install -y python3-pip redis-server nginx

# Clonar repo
git clone <repo-url> /opt/mma-predictor
cd /opt/mma-predictor/api

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar .env
nano .env
# Agregar ANTHROPIC_API_KEY

# Configurar Nginx
sudo nano /etc/nginx/sites-available/mma-api
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health/llm;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/mma-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Iniciar API (usar systemd service de arriba)
```

## 🔐 Security Checklist

- [ ] `ANTHROPIC_API_KEY` en variables de entorno (no en código)
- [ ] `.env` en `.gitignore`
- [ ] Redis con password en producción
- [ ] Rate limiting en Nginx/API
- [ ] HTTPS con Let's Encrypt
- [ ] Firewall configurado (solo 80, 443, 22)
- [ ] Logs rotados (logrotate)
- [ ] Backups automáticos de modelos/datos

## 📊 Monitoreo

### Prometheus + Grafana

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mma-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Healthchecks

```bash
# Healthcheck script
cat > healthcheck.sh << 'EOF'
#!/bin/bash
HEALTH=$(curl -s http://localhost:8000/health/llm | jq -r '.status')
if [ "$HEALTH" != "healthy" ]; then
    echo "CRITICAL: LLM health check failed"
    # Alertar (email, Slack, PagerDuty, etc.)
    exit 1
fi
EOF

chmod +x healthcheck.sh

# Cron (cada 5 minutos)
*/5 * * * * /opt/mma-predictor/healthcheck.sh
```

### Uptime monitoring

```bash
# Usar servicios externos
# - UptimeRobot: https://uptimerobot.com/
# - Pingdom: https://www.pingdom.com/
# - StatusCake: https://www.statuscake.com/

# O self-hosted
docker run -d --name uptime-kuma \
  -p 3001:3001 \
  -v uptime-kuma:/app/data \
  louislam/uptime-kuma:1
```

## 🐛 Troubleshooting Production

### Logs importantes

```bash
# Logs de la API
tail -f /var/log/mma-api/app.log

# Logs de Redis
tail -f /var/log/redis/redis-server.log

# Logs de Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Logs de Systemd
journalctl -u mma-api -n 100 --no-pager
```

### Reinicio de servicios

```bash
# Reinicio graceful
sudo systemctl reload mma-api

# Reinicio completo
sudo systemctl restart mma-api
sudo systemctl restart redis
sudo systemctl restart nginx

# Verificar status
sudo systemctl status mma-api
```

### Problemas comunes

**API no responde**
```bash
# Verificar proceso
ps aux | grep python

# Verificar puerto
sudo netstat -tlnp | grep 8000

# Verificar firewall
sudo ufw status
sudo ufw allow 8000
```

**Claude siempre usa fallback**
```bash
# Test directo de API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-5-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# Revisar cuota
# Ir a https://console.anthropic.com/settings/billing
```

**Ollama no responde**
```bash
# Verificar servicio
sudo systemctl status ollama

# Verificar proceso
ps aux | grep ollama

# Logs
journalctl -u ollama -f

# Reiniciar
sudo systemctl restart ollama
```

## 📈 Escalabilidad

### Horizontal scaling (múltiples instancias)

```bash
# Load balancer (Nginx)
upstream mma_api {
    least_conn;
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    server 10.0.1.12:8000;
}

server {
    location / {
        proxy_pass http://mma_api;
    }
}
```

### Redis cluster

```bash
# Para alta disponibilidad
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  --cluster-replicas 1
```

### Optimizaciones

1. **Cache agresivo**: Aumentar TTL de Redis a 24h
2. **Async workers**: Usar Gunicorn con workers async
3. **CDN**: CloudFlare para frontend estático
4. **Database read replicas**: Para consultas de fighters

---

**Última actualización**: 2025-10-06
