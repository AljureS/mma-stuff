#!/usr/bin/env bash
# Prerrequisitos del homelab para el MMA Fight Predictor. Idempotente. Correr como:
#   ssh -t simon@homelab 'sudo bash ~/setup/mma_prereqs.sh'
# NO toca sshd, ufw, red, authorized_keys ni Tailscale ACLs.
set -euo pipefail
U=simon
echo "== estado antes"; command -v docker || true; id "$U"; tailscale status --self 2>/dev/null | head -1 || true

echo "== guardas antes de cambiar nada"
if dpkg -s docker.io >/dev/null 2>&1 || dpkg -s podman-docker >/dev/null 2>&1; then
  echo "ABORTO: hay docker.io/podman-docker de Debian instalado; conflictúa con docker-ce. Desinstalalo a mano y re-corré." >&2
  exit 1
fi

echo "== paquetes base (rsync, curl, ca-certificates)"
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl rsync

echo "== Docker desde el repo oficial (paso 10 del plan)"
# Idempotente: instala/completa si falta el Engine oficial o el plugin Compose (instalación parcial)
if ! dpkg -s docker-ce docker-compose-plugin >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$U"

echo "== Tailscale: simon puede operar 'tailscale serve' sin sudo"
tailscale set --operator="$U"

echo "== Tapa cerrada NO suspende (paso 9 del plan): logind ignora la tapa + targets de sleep enmascarados"
install -d /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/10-homelab-lid.conf <<'CONF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
CONF
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
systemctl kill -s HUP systemd-logind

echo "== estado después"
docker --version; docker compose version
id "$U"
systemctl is-active docker
systemctl is-enabled suspend.target || true
echo "OK. Cerrá la sesión SSH y volvé a entrar para que el grupo docker aplique."
