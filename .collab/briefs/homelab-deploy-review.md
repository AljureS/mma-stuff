# Brief (HalJordan, REVIEW read-only): revisar los cambios sin commitear del deploy al homelab

Sos el revisor independiente (consenso Muad'Dib ↔ HalJordan). NO edites nada. Revisá `git diff` + archivos nuevos no trackeados: api/main.py, frontend/index.js, Dockerfile, .dockerignore, compose.yaml, CLAUDE.md, README.md, tasks/todo.md, tasks/deploy/verify_plan.sh, tasks/deploy/mma_prereqs.sh, tasks/deploy/tailnet-policy.hujson.

Contexto: el proyecto se copiará a un Debian 13 x86_64 (6 GB RAM, usuario simon uid 1000) y se servirá SOLO dentro del tailnet vía `tailscale serve --bg 8000` (HTTPS en homelab:443 → 127.0.0.1:8000). Todos los devices del tailnet son del mismo usuario; la restricción "solo el MacBook" se hace con una grant por host IP. El server tiene password SSH y un agente no puede usar sudo: mma_prereqs.sh lo corre el humano con sudo.

Foco:
1. Exposición: ¿algo publica fuera de 127.0.0.1 o queda accesible sin Tailscale? (Docker se salta ufw)
2. Secretos: ¿api/.env podría terminar en la imagen, en git o impreso?
3. Correctitud: Redis via REDIS_URL; /ui StaticFiles sin romper GET / ni otros endpoints; API_BASE_URL same-origin con fallback dev.
4. compose: CSV escrito en runtime por uid 1000 en ./data; models ro; healthcheck; límites de RAM razonables en 6 GB.
5. mma_prereqs.sh: idempotente, `set -euo pipefail`, ¿algo puede dejar el server inaccesible o romper SSH/Tailscale? ¿Docker repo correcto para trixie?
6. tailnet-policy.hujson: sintaxis válida de Tailscale policy (hosts/grants/tests), ¿realmente limita a solo el MacBook y no bloquea algo necesario (p. ej. el propio serve)?
7. verify_plan.sh: ¿detecta de verdad borrados en la Mac, cambios fuera de scope, puertos en 0.0.0.0 y funnel? falsos positivos/negativos.

Reporte: lista de hallazgos con severidad (BLOCKER/HIGH/MEDIUM/LOW), archivo:línea, escenario de falla y fix sugerido. Terminá con una línea exacta: `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS FOUND`.
