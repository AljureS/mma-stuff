#!/usr/bin/env bash
# Verificador del plan de deploy (lo corre el /loop). Solo lectura. Exit 0 = plan íntegro.
cd "$(dirname "$0")/../.." || exit 2
fail=0; say(){ echo "$1"; }
MANIFEST=tasks/baselines/deploy_manifest.sha256
BASEFILE=tasks/baselines/deploy_base_commit
SRV_BASE=tasks/baselines/server_listeners.txt
# Archivos que el plan autoriza a crear/modificar (enumerados; api/.env solo se des-trackea, sigue en disco)
SCOPE='^(api/main\.py|api/\.env|frontend/index\.js|Dockerfile|\.dockerignore|compose\.yaml|CLAUDE\.md|README\.md|tasks/todo\.md|tasks/lessons\.md|tasks/deploy/(verify_plan\.sh|mma_prereqs\.sh|tailnet-policy\.hujson|evidence/[A-C][0-9]+\.txt)|\.collab/(briefs|delegations|reviews)/[^/]+|data/fighters_complete\.csv|\.gitignore)$'
# 0) Baselines obligatorias
[ -s "$MANIFEST" ] || { echo "FAIL: falta el manifest $MANIFEST"; echo "PLAN CORRUPTO $(date '+%F %T')"; exit 1; }
BASE=$(cat "$BASEFILE" 2>/dev/null); git cat-file -e "${BASE:-x}^{commit}" 2>/dev/null || { echo "FAIL: commit base inválido o ausente ($BASEFILE)"; echo "PLAN CORRUPTO $(date '+%F %T')"; exit 1; }
# 1) Mac: ningún archivo de la baseline desapareció; fuera del scope, contenido idéntico
while read -r sum path; do
  p="${path#./}"
  if [ ! -f "$path" ]; then say "FAIL: falta $p (borrado en la Mac)"; fail=1; continue; fi
  if ! echo "$p" | grep -Eq "$SCOPE"; then
    [ "$(shasum -a 256 "$path" | cut -d' ' -f1)" = "$sum" ] || { say "FAIL: $p cambió y está fuera del scope"; fail=1; }
  fi
done < "$MANIFEST"
[ -d venv ] && [ -f models/mma_prediction_model.pkl ] && [ -f data/fighters_complete.csv ] && [ -f api/.env ] || { say "FAIL: falta venv/pkl/csv/.env local"; fail=1; }
# 2) git: cambios (trackeados, untracked y commits nuevos desde base) dentro del scope
out=$( { git diff --name-only "$BASE"; git ls-files --others --exclude-standard; } | sort -u | grep -Ev "$SCOPE" )
[ -z "$out" ] || { say "FAIL: cambios fuera de scope: $(echo $out)"; fail=1; }
# 3) Tailscale local: nunca funnel (JSON estructurado)
if ! mfun=$(tailscale funnel status --json 2>/dev/null) || ! echo "$mfun" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
  say "FAIL: no se pudo consultar funnel en la Mac"; fail=1
elif echo "$mfun" | grep -q '"AllowFunnel"'; then say "FAIL: funnel configurado en la Mac"; fail=1; fi
# 4) Server: obligatorio desde que C1 está marcado (antes es informativo)
plan=$(sed -n '/^# Plan: Deploy al Home Lab/,/^## Review/p' tasks/todo.md)
deployed=0; echo "$plan" | grep -Eq '^- \[x\] C1 ' && deployed=1
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 simon@homelab"
if $SSH true 2>/dev/null; then
  cur=$($SSH 'ss -tulnH | awk "{print \$1, \$5}" | sort -u') || { say "FAIL: no se pudo leer listeners del server"; fail=1; }
  fun=$($SSH 'tailscale funnel status --json 2>/dev/null') || { say "FAIL: no se pudo leer funnel del server"; fail=1; }
  if [ ! -s "$SRV_BASE" ]; then
    if [ $deployed -eq 0 ]; then echo "$cur" > "$SRV_BASE"; say "info: baseline de listeners del server capturada (pre-deploy)"
    else say "FAIL: falta baseline de listeners del server y ya hubo deploy"; fail=1; fi
  fi
  if [ -s "$SRV_BASE" ]; then
    # Nuevos listeners permitidos: solo loopback (docker 127.0.0.1:8000) y la IP de Tailscale (serve :443/:80)
    new=$(comm -13 "$SRV_BASE" <(echo "$cur") | grep -Ev ' (127\.0\.0\.1|\[::1\]|100\.99\.75\.17|\[fd7a:115c:a1e0:[0-9a-f:]*\]):[0-9]+$')
    [ -z "$new" ] && say "ok: server sin listeners nuevos fuera de loopback/tailnet" || { say "FAIL: server expone nuevos listeners: $(echo $new)"; fail=1; }
  fi
  if ! echo "$fun" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then say "FAIL: respuesta de funnel del server no es JSON válido"; fail=1
  elif echo "$fun" | grep -q '"AllowFunnel"'; then say "FAIL: funnel configurado en homelab"; fail=1; fi
elif [ $deployed -eq 1 ]; then
  say "FAIL: homelab inaccesible por ssh después del deploy (no se puede verificar exposición)"; fail=1
else
  say "info: homelab no accesible por ssh con llave (pendiente B1/B2)"
fi
# 5) Items marcados [x] en el plan de deploy deben tener evidencia
for id in $(echo "$plan" | grep -Eo '^- \[x\] [A-C][0-9]+' | awk '{print $3}'); do
  [ -s "tasks/deploy/evidence/$id.txt" ] || { say "FAIL: $id marcado sin evidencia (tasks/deploy/evidence/$id.txt)"; fail=1; }
done
[ $fail -eq 0 ] && echo "PLAN OK $(date '+%F %T')" || echo "PLAN CORRUPTO $(date '+%F %T')"
exit $fail
