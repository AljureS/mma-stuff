# Lecciones Aprendidas

> Registro de correcciones del usuario y patrones a no repetir.
> Regla: tras CUALQUIER corrección del usuario, agregar aquí el patrón y la regla que lo previene.
> Revisar este archivo al inicio de cada sesión.

## Reglas activas

- (2026-07-01) El plugin `skill-creator` existe en el marketplace local (`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator`) pero no está habilitado como skill invocable; para crear skills, seguir su metodología leyendo su SKILL.md directamente.

- (2026-09-26) Wrappers de la skill collab-haljordan-muaddib en macOS: bash 3.2 revienta con `"${arr[@]}"` vacío bajo `set -u` (parcheado a `${arr[@]+"${arr[@]}"}`), y `codex exec` sin `</dev/null` se cuelga en "Reading additional input from stdin". `codex review --uncommitted` no acepta prompt de foco: para reviews con foco usar `codex_delegate.sh --sandbox read-only` con un brief de review.
- (2026-09-26) Los logs crudos de Codex (`.collab/delegations/*-stdout.log`) pueden contener secretos que Codex leyó del workspace (pasó con la key de OpenAI). Están en .gitignore; antes de commitear `.collab/`, verificar por VALOR que ningún valor de `api/.env` aparece.
- (2026-09-26) `api/.env` estuvo trackeado y pusheado a un repo público pese a `.env` en .gitignore (se agregó antes de la regla). Chequear `git ls-files | grep .env` en cualquier auditoría.

## Correcciones

- (2026-09-26) Usé `~/.ssh/id_ed25519` para el homelab sin revisar su comentario: es la llave del correo de TRABAJO (code@primecredential.com). **Regla:** el homelab es personal. Usar solo `~/.ssh/id_ed25519_homelab` (comentario saidsimon2@gmail.com) con `-o IdentitiesOnly=yes`; antes de proponer cualquier llave o identidad, leer su comentario/email y confirmar que corresponde al contexto (personal vs trabajo).

- (2026-09-26) Le pedí al usuario correr `! ssh-copy-id` dentro de Claude Code: el prefijo `!` no ofrece prompt de contraseña, así que falla siempre con `Permission denied`. **Regla:** todo comando que pida contraseña, passphrase o `yes/no` (ssh-copy-id, ssh interactivo, sudo) se indica para Terminal.app, nunca con `!`. Además, cuando un goal queda bloqueado por un paso humano, decirlo una vez con instrucciones exactas y no responder en bucle.

- (2026-09-26) Los scripts de la skill collab-haljordan-muaddib en `~/.claude/skills/synced/...` pueden perder el bit de ejecución (exit 126 "permission denied"): invocarlos siempre con `bash <script>`. Y en macOS no existe `timeout` (el wrapper corre sin límite; usar `perl -e 'alarm N; exec @ARGV' cmd` para el lector de usage).
- (2026-09-26) Claude in Chrome: tras `navigate`, el foco queda en la omnibox y `computer type` no llega a la página aunque se haga `element.focus()` por JS; hacer `left_click` sobre el input antes de tipear. Los `key`/`type` corren antes de que termine un debounce+fetch: esperar 1–2 s antes de leer el estado del DOM.
- (2026-09-26, tarde) El `codex_delegate.sh` de la copia SINCRONIZADA de la skill (`~/.claude/skills/synced/...`) NO redirige stdin: un `codex exec` puede quedarse colgado en "Reading additional input from stdin..." (pasó en la ronda 3 de review: 21 min con un log de 39 bytes). Invocar SIEMPRE `bash codex_delegate.sh ... </dev/null`, y si un log de `.collab/delegations/*-stdout.log` no crece en 2–3 min, matar el `codex exec` (`pgrep -fl 'codex exec'`), anotarlo en el registro y relanzar.
