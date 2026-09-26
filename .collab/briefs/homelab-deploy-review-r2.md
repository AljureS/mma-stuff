# Brief (HalJordan, REVIEW read-only, ronda 2): re-revisar tras tus hallazgos de la ronda 1

Ronda 1 (tu review en .collab/delegations/20260926T*-last-message.md, VERDICT: BLOCKERS FOUND). Muad'Dib aplicó:
1. BLOCKER api/.env trackeado: `git rm --cached api/.env` (queda en disco; .gitignore ya lo cubre). La rotación de credenciales y la purga del historial remoto son acciones del owner (no del repo) — están documentadas en CLAUDE.md y se le reportan. Evaluá si el diff del repo ya no introduce ni mantiene el secreto.
2. verify_plan.sh: scope enumerado; falla si faltan manifest/commit base; server obligatorio tras C1; listeners TCP+UDP comparados contra baseline pre-deploy (solo se permiten nuevos en loopback / IP de Tailscale); funnel vía `--json`.
3. mma_prereqs.sh: aborta si hay docker.io/podman-docker; instala/completa si falta docker-ce o compose plugin.
4. compose.yaml: healthcheck redis + api (models_loaded, fighters_count>0, redis ping), depends_on service_healthy.
5. tailnet-policy.hujson: host de prueba `otro-device` con tests deny.
6. api/main.py: CORS desde CORS_ORIGINS con default localhost:3000/127.0.0.1:3000.

Verificado por Muad'Dib: pytest 15 passed; /predict = 0.7760478854179382; preflight desde http://localhost:3000 -> 200 con ACAO, desde https://evil.example -> 400; /ui/ 200; verifier con tests negativos (archivo fuera de scope y base ausente -> PLAN CORRUPTO).

NO edites nada. Revisá `git diff --cached` + `git diff` + untracked de los archivos del deploy. Mismo formato: hallazgos con severidad (BLOCKER/HIGH/MEDIUM/LOW), archivo:línea, escenario y fix. Solo marcá BLOCKER/HIGH lo que realmente está en scope del repo. Última línea exacta: `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS FOUND`.
