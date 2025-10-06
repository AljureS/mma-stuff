#!/bin/bash

# MMA Fight Predictor - Complete Deployment Setup
# Este script configura todo el stack necesario

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables de configuración
PROJECT_NAME="mma-predictor"
DOMAIN="your-domain.com"  # Cambiar por tu dominio
API_PORT=8000
FRONTEND_PORT=3000
POSTGRES_PASSWORD="your_secure_password"
REDIS_PASSWORD="your_redis_password"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Verificar prerrequisitos
check_prerequisites() {
    print_section "Verificando Prerrequisitos"
    
    # Verificar SO
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "Este script solo funciona en Linux"
        exit 1
    fi
    
    # Verificar permisos
    if [[ $EUID -eq 0 ]]; then
        print_error "No ejecutes este script como root"
        exit 1
    fi
    
    # Verificar espacio en disco (mínimo 10GB)
    available_space=$(df . | tail -1 | awk '{print $4}')
    min_space=$((10 * 1024 * 1024)) # 10GB en KB
    
    if [[ $available_space -lt $min_space ]]; then
        print_error "Necesitas al menos 10GB de espacio libre"
        exit 1
    fi
    
    # Verificar RAM (mínimo 4GB)
    total_ram=$(free -m | awk 'NR==2{printf "%.0f", $2/1024}')
    if [[ $total_ram -lt 4 ]]; then
        print_warning "Se recomiendan al menos 4GB de RAM"
    fi
    
    print_status "Prerrequisitos verificados ✓"
}

# Instalar dependencias del sistema
install_system_dependencies() {
    print_section "Instalando Dependencias del Sistema"
    
    # Actualizar sistema
    sudo apt update && sudo apt upgrade -y
    
    # Instalar dependencias básicas
    sudo apt install -y curl wget git build-essential software-properties-common \
                        apt-transport-https ca-certificates gnupg lsb-release \
                        python3 python3-pip python3-venv postgresql postgresql-contrib \
                        nginx redis-server supervisor htop tree
    
    # Instalar Node.js 18
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
    
    # Instalar Docker
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt update
        sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        sudo usermod -aG docker $USER
    fi
    
    # Instalar Ollama
    if ! command -v ollama &> /dev/null; then
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
    
    print_status "Dependencias del sistema instaladas ✓"
}

# Crear estructura del proyecto
create_project_structure() {
    print_section "Creando Estructura del Proyecto"
    
    mkdir -p $PROJECT_NAME/{api,frontend,data,models,logs,scripts,config}
    cd $PROJECT_NAME
    
    # Crear directorios adicionales
    mkdir -p {data/{raw,processed,models},logs/{api,nginx,ollama},config/{nginx,supervisor}}
    
    print_status "Estructura del proyecto creada en $(pwd) ✓"
}

# Configurar base de datos
setup_database() {
    print_section "Configurando Base de Datos PostgreSQL"
    
    # Crear usuario y base de datos
    sudo -u postgres psql -c "CREATE USER mma_user WITH PASSWORD '$POSTGRES_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE mma_predictions OWNER mma_user;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mma_predictions TO mma_user;"
    
    # Crear tabla inicial
    cat > config/init_db.sql << EOF
-- Tabla de luchadores
CREATE TABLE fighters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    height FLOAT,
    reach FLOAT,
    age INTEGER,
    weight_class VARCHAR(50),
    ranking INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de peleas
CREATE TABLE fights (
    id SERIAL PRIMARY KEY,
    fighter_a_id INTEGER REFERENCES fighters(id),
    fighter_b_id INTEGER REFERENCES fighters(id),
    event_name VARCHAR(255),
    fight_date DATE,
    result VARCHAR(10), -- 'A', 'B', 'Draw', 'NC'
    method VARCHAR(50),
    round INTEGER,
    time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de predicciones
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    fight_id INTEGER REFERENCES fights(id),
    fighter_a_probability FLOAT,
    fighter_b_probability FLOAT,
    predicted_winner VARCHAR(10),
    confidence FLOAT,
    model_version VARCHAR(50),
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX idx_fighters_name ON fighters(name);
CREATE INDEX idx_fights_date ON fights(fight_date);
CREATE INDEX idx_predictions_date ON predictions(prediction_date);
EOF

    # Ejecutar script de inicialización
    PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U mma_user -d mma_predictions -f config/init_db.sql
    
    print_status "Base de datos configurada ✓"
}

# Configurar Redis
setup_redis() {
    print_section "Configurando Redis"
    
    # Configurar Redis con password
    sudo sed -i "s/# requirepass foobared/requirepass $REDIS_PASSWORD/" /etc/redis/redis.conf
    sudo systemctl restart redis-server
    sudo systemctl enable redis-server
    
    print_status "Redis configurado ✓"
}

# Configurar API backend
setup_api() {
    print_section "Configurando API Backend"
    
    cd api
    
    # Crear entorno virtual Python
    python3 -m venv venv
    source venv/bin/activate
    
    # Crear requirements.txt
    cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
xgboost==1.7.6
lightgbm==4.1.0
psycopg2-binary==2.9.7
redis==5.0.1
aiohttp==3.8.6
beautifulsoup4==4.12.2
requests==2.31.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
prometheus-client==0.17.1
structlog==23.1.0
EOF
    
    # Instalar dependencias
    pip install -r requirements.txt
    
    # Crear archivo de configuración
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://mma_user:$POSTGRES_PASSWORD@localhost/mma_predictions

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=$REDIS_PASSWORD

# API
API_HOST=0.0.0.0
API_PORT=$API_PORT
API_WORKERS=4

# Ollama
OLLAMA_URL=http://localhost:11434

# Security
SECRET_KEY=$(openssl rand -hex 32)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External APIs
ODDS_API_KEY=your_odds_api_key
TWITTER_BEARER_TOKEN=your_twitter_token

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/mma-predictor/api.log
EOF
    
    print_status "API backend configurada ✓"
    cd ..
}

# Configurar frontend
setup_frontend() {
    print_section "Configurando Frontend"
    
    cd frontend
    
    # Crear package.json
    cat > package.json << EOF
{
  "name": "mma-predictor-frontend",
  "version": "1.0.0",
  "description": "Frontend para MMA Fight Predictor",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js",
    "build": "echo 'Static site - no build needed'"
  },
  "dependencies": {
    "express": "^4.18.2",
    "compression": "^1.7.4",
    "helmet": "^7.1.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}
EOF
    
    # Crear servidor Express simple
    cat > server.js << EOF
const express = require('express');
const path = require('path');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || $FRONTEND_PORT;

// Middlewares de seguridad
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://cdnjs.cloudflare.com"],
            scriptSrc: ["'self'", "https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net"],
            imgSrc: ["'self'", "data:", "https:"],
            connectSrc: ["'self'", "http://localhost:$API_PORT", "https://api.your-domain.com"]
        },
    },
}));

app.use(compression());
app.use(express.static(path.join(__dirname, 'public')));

// Servir index.html
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
    console.log(\`Frontend server running on port \${PORT}\`);
});
EOF
    
    # Instalar dependencias
    npm install
    
    # Crear directorio público y copiar HTML
    mkdir -p public
    # Aquí copiarías el HTML del artifact anterior
    
    print_status "Frontend configurado ✓"
    cd ..
}

# Configurar Nginx
setup_nginx() {
    print_section "Configurando Nginx"
    
    # Crear configuración de Nginx
    cat > config/nginx/mma-predictor.conf << EOF
# Upstream para API
upstream api_backend {
    server 127.0.0.1:$API_PORT;
}

# Upstream para frontend
upstream frontend_backend {
    server 127.0.0.1:$FRONTEND_PORT;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;
    
    # SSL configuration (se configurará con certbot)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    # ssl_session_cache shared:le_nginx_SSL:10m;
    # ssl_session_timeout 1440m;
    # ssl_session_tickets off;
    # ssl_protocols TLSv1.2 TLSv1.3;
    # ssl_prefer_server_ciphers off;
    # ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # API routes
    location /api/ {
        proxy_pass http://api_backend/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # CORS headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS';
        add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
        
        # Handle preflight requests
        if (\$request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS';
            add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
            add_header Access-Control-Max-Age 1728000;
            add_header Content-Type 'text/plain; charset=utf-8';
            add_header Content-Length 0;
            return 204;
        }
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Frontend routes
    location / {
        proxy_pass http://frontend_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
    
    # Static files with caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        proxy_pass http://frontend_backend;
    }
    
    # Health checks
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF
    
    # Copiar configuración a Nginx
    sudo cp config/nginx/mma-predictor.conf /etc/nginx/sites-available/
    sudo ln -sf /etc/nginx/sites-available/mma-predictor.conf /etc/nginx/sites-enabled/
    
    # Remover configuración por defecto
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Crear directorio para challenges de Let's Encrypt
    sudo mkdir -p /var/www/letsencrypt
    
    print_status "Nginx configurado ✓"
}

# Configurar servicios systemd
setup_services() {
    print_section "Configurando Servicios Systemd"
    
    # Servicio para API
    cat > config/mma-predictor-api.service << EOF
[Unit]
Description=MMA Predictor API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/api
Environment=PATH=$(pwd)/api/venv/bin
ExecStart=$(pwd)/api/venv/bin/uvicorn main:app --host 0.0.0.0 --port $API_PORT --workers 4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Servicio para frontend
    cat > config/mma-predictor-frontend.service << EOF
[Unit]
Description=MMA Predictor Frontend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/frontend
ExecStart=/usr/bin/node server.js
Environment=NODE_ENV=production
Environment=PORT=$FRONTEND_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Servicio para Ollama
    cat > config/mma-predictor-ollama.service << EOF
[Unit]
Description=MMA Predictor Ollama Service
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/ollama serve
Environment=OLLAMA_HOST=127.0.0.1:11434
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Copiar servicios
    sudo cp config/*.service /etc/systemd/system/
    
    # Recargar systemd y habilitar servicios
    sudo systemctl daemon-reload
    sudo systemctl enable mma-predictor-api.service
    sudo systemctl enable mma-predictor-frontend.service
    sudo systemctl enable mma-predictor-ollama.service
    
    print_status "Servicios configurados ✓"
}

# Configurar SSL con Let's Encrypt
setup_ssl() {
    print_section "Configurando SSL con Let's Encrypt"
    
    # Instalar certbot
    sudo apt install -y certbot python3-certbot-nginx
    
    # Obtener certificado
    print_warning "Asegúrate de que tu dominio $DOMAIN apunte a esta IP"
    print_warning "Presiona Enter cuando esté listo o Ctrl+C para cancelar"
    read -r
    
    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    
    # Configurar renovación automática
    sudo crontab -l | { cat; echo "0 12 * * * /usr/bin/certbot renew --quiet"; } | sudo crontab -
    
    print_status "SSL configurado ✓"
}

# Configurar monitoreo
setup_monitoring() {
    print_section "Configurando Monitoreo"
    
    # Script de monitoreo básico
    cat > scripts/monitor.sh << 'EOF'
#!/bin/bash

# Verificar servicios
services=("mma-predictor-api" "mma-predictor-frontend" "mma-predictor-ollama" "nginx" "postgresql" "redis-server")

for service in "${services[@]}"; do
    if ! systemctl is-active --quiet $service; then
        echo "$(date): $service is down" >> logs/monitoring.log
        # Aquí podrías enviar una notificación
    fi
done

# Verificar espacio en disco
disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $disk_usage -gt 90 ]; then
    echo "$(date): Disk usage is $disk_usage%" >> logs/monitoring.log
fi

# Verificar memoria
mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $mem_usage -gt 90 ]; then
    echo "$(date): Memory usage is $mem_usage%" >> logs/monitoring.log
fi
EOF
    
    chmod +x scripts/monitor.sh
    
    # Configurar cron para monitoreo
    (crontab -l 2>/dev/null; echo "*/5 * * * * $(pwd)/scripts/monitor.sh") | crontab -
    
    print_status "Monitoreo configurado ✓"
}

# Descargar modelos
download_models() {
    print_section "Descargando Modelos"
    
    # Iniciar Ollama
    sudo systemctl start mma-predictor-ollama
    sleep 10
    
    # Descargar modelo GPT-OSS
    print_warning "Descargando modelo gpt-oss-20b (esto puede tardar varios minutos)..."
    ollama pull gpt-oss-20b
    
    print_status "Modelos descargados ✓"
}

# Inicializar datos
initialize_data() {
    print_section "Inicializando Datos"
    
    cd api
    source venv/bin/activate
    
    # Script de inicialización de datos (placeholder)
    cat > init_data.py << 'EOF'
#!/usr/bin/env python3
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Conectar a la base de datos
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Insertar algunos luchadores de ejemplo
fighters_data = [
    ('Jon Jones', 27, 1, 0, 193, 215, 36, 'heavyweight', 1),
    ('Stipe Miocic', 20, 4, 0, 193, 203, 41, 'heavyweight', 2),
    ('Alexander Volkanovski', 26, 3, 0, 168, 183, 35, 'featherweight', 1),
    ('Ilia Topuria', 15, 0, 0, 170, 178, 27, 'featherweight', 2)
]

for fighter in fighters_data:
    cur.execute("""
        INSERT INTO fighters (name, wins, losses, draws, height, reach, age, weight_class, ranking) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO NOTHING
    """, fighter)

conn.commit()
cur.close()
conn.close()

print("Sample data inserted successfully!")
EOF
    
    python init_data.py
    
    print_status "Datos inicializados ✓"
    cd ..
}

# Función principal
main() {
    print_section "MMA Fight Predictor - Deployment Setup"
    print_status "Iniciando configuración completa del sistema..."
    
    # Crear log del deployment
    exec 1> >(tee -a deployment.log)
    exec 2>&1
    
    # Ejecutar pasos
    check_prerequisites
    install_system_dependencies
    create_project_structure
    setup_database
    setup_redis
    setup_api
    setup_frontend
    setup_nginx
    setup_services
    setup_monitoring
    download_models
    initialize_data
    
    # Iniciar servicios
    print_section "Iniciando Servicios"
    sudo systemctl start mma-predictor-ollama
    sleep 10
    sudo systemctl start mma-predictor-api
    sudo systemctl start mma-predictor-frontend
    sudo systemctl restart nginx
    
    # Verificar estado
    print_section "Verificando Estado"
    services=("mma-predictor-api" "mma-predictor-frontend" "mma-predictor-ollama" "nginx" "postgresql" "redis-server")
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet $service; then
            print_status "$service está ejecutándose ✓"
        else
            print_error "$service no está ejecutándose ❌"
        fi
    done
    
    # Información final
    print_section "🎉 ¡Deployment Completado!"
    echo ""
    print_status "Tu sistema MMA Fight Predictor está listo:"
    echo ""
    echo "🌐 Frontend: http://$(curl -s ipecho.net/plain):$FRONTEND_PORT"
    echo "🔌 API: http://$(curl -s ipecho.net/plain):$API_PORT/docs"
    echo "🤖 Ollama: http://localhost:11434"
    echo ""
    echo "📊 Monitoreo:"
    echo "  - Logs API: sudo journalctl -u mma-predictor-api -f"
    echo "  - Logs Frontend: sudo journalctl -u mma-predictor-frontend -f" 
    echo "  - Logs Nginx: sudo tail -f /var/log/nginx/access.log"
    echo ""
    echo "🔧 Comandos útiles:"
    echo "  - Reiniciar API: sudo systemctl restart mma-predictor-api"
    echo "  - Ver estado: sudo systemctl status mma-predictor-api"
    echo "  - Logs en tiempo real: tail -f logs/monitoring.log"
    echo ""
    print_warning "Próximos pasos:"
    echo "1. Configurar tu dominio ($DOMAIN) para apuntar a esta IP"
    echo "2. Ejecutar: sudo $0 --ssl-only para configurar SSL"
    echo "3. Recolectar datos históricos de peleas"
    echo "4. Entrenar tu modelo con datos reales"
    echo ""
    print_status "¡Disfruta prediciendo peleas de MMA! 🥊"
}

# Función para solo SSL
setup_ssl_only() {
    if [[ "$1" == "--ssl-only" ]]; then
        setup_ssl
        sudo systemctl reload nginx
        exit 0
    fi
}

# Verificar argumentos
setup_ssl_only "$1"

# Ejecutar función principal
main "$@"