# Brief (HalJordan): preparar el repo para correr en Docker en el homelab detrás de tailscale serve

Objective: que el proyecto corra con `docker compose up -d --build` en un Debian x86_64 (6 GB RAM) sirviendo API + frontend en un único origen `127.0.0.1:8000`, sin romper el flujo local actual.

## Cambios exactos
1. `api/main.py`
   - Redis: reemplazar `redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)` por `redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)` (importar `os` arriba; `load_dotenv()` ya corre antes). El `.env` local tiene `REDIS_URL=redis://localhost:6379` -> comportamiento local idéntico.
   - Servir el frontend: `from fastapi.staticfiles import StaticFiles`; `FRONTEND_DIR = Path(__file__).parent.parent / "frontend"`; si existe, `app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")`. NO tocar `GET /` (sigue siendo el health check) ni ningún otro endpoint, features, cache o LLM.
2. `frontend/index.js` línea 2: `API_BASE_URL` = `window.location.origin` cuando la página se sirve por http(s) desde un puerto distinto de 3000; `'http://localhost:8000'` cuando `location.protocol === 'file:'` o `location.port === '3000'` (dev local con `python -m http.server 3000`). Nada más en el frontend.
3. `Dockerfile` (raíz): `python:3.11-slim` (el pkl se generó con Python 3.11.14 + xgboost 1.7.6 + scikit-learn 1.3.0), `apt-get install -y --no-install-recommends libgomp1` (xgboost), `pip install --no-cache-dir -r api/requirements.txt`, copia `api/`, `scripts/`, `frontend/` a `/app/...`. NO copiar `data/`, `models/`, `.env`. `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/api"]` (no usar `python main.py`: el .env tiene DEBUG=true y activaría reload).
4. `.dockerignore`: `venv/`, `api/venv/`, `.git/`, `.pytest_cache/`, `**/__pycache__/`, `**/*.pyc`, `api/.env`, `.env`, `data/`, `models/`, `tasks/`, `.claude/`, `.collab/`, `docs/`, `.DS_Store`, `dump.rdb`.
5. `compose.yaml` (raíz), proyecto `mma`:
   - `redis`: `redis:7-alpine`, `command: redis-server --save "" --appendonly no --maxmemory 128mb --maxmemory-policy allkeys-lru`, SIN `ports`, `restart: unless-stopped`, `mem_limit: 256m`.
   - `api`: `build: .`, `env_file: api/.env`, `environment: REDIS_URL: redis://redis:6379/0` (pisa el .env), `ports: ["127.0.0.1:8000:8000"]` (JAMÁS 0.0.0.0), `volumes: ./data:/app/data` (rw: la API escribe el CSV en runtime) y `./models:/app/models:ro`, `user: "${UID:-1000}:${GID:-1000}"`, `depends_on: [redis]`, `restart: unless-stopped`, `mem_limit: 1g`, `healthcheck` con `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"`.

## Archivos que te pertenecen (no edites nada más)
api/main.py, frontend/index.js, Dockerfile, .dockerignore, compose.yaml

## Contexto a leer primero
CLAUDE.md (contratos: 16 features, `probabilities[1]`, CSV escrito en runtime, sys.path hack), api/main.py, frontend/index.js, frontend/index.html.

## No hacer
No tocar `.env*`, CLAUDE.md, README, tasks/, tests/, scripts/, data/, models/. No agregar dependencias a requirements.txt (StaticFiles viene con FastAPI/starlette). No correr nada bajo scripts/. No commitear. No borrar archivos.

## Tests (verde = todo pasa)
- `venv/bin/python -m pytest tests/test_llm_client.py -q` -> 15 passed
- `venv/bin/python -c "import ast,sys; ast.parse(open('api/main.py').read())"` -> sin error
- `node --check frontend/index.js` -> sin error
- `docker compose config -q` -> exit 0 (si el daemon/CLI no está disponible en tu sandbox, reportalo como skipped)

## Reporte
Archivos cambiados, comandos corridos con resultado y el `git status` contra el que corrieron, lo que saltaste y por qué, preguntas abiertas.
