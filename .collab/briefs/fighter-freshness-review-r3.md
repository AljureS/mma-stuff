# Brief (HalJordan): REVIEW ronda 3 (última) — frescura de datos de peleadores (solo lectura)

Tercera y última ronda del gate de consenso (tope 3; si no hay consenso, decide el owner). NO edites archivos. Alcance: SOLO el HIGH que quedó abierto en tu ronda 2 y regresiones directas de su corrección en `frontend/index.js` (`verifyFighterFreshness`, `refreshFighter`, `clearFighterUI`, `searchState`). Todo lo demás ya quedó "resuelto" en R2 y no se reabre salvo que la corrección lo rompa.

## Hallazgo R2
HIGH — verificar X (completada), seleccionar Y y volver a X mientras Y está en vuelo: `verifiedName === X` saltaba la verificación, la respuesta de Y se descartaba por secuencia y el sello quedaba en "Verificando…" con el botón deshabilitado.

## Corrección (frontend/index.js, `verifyFighterFreshness`)
Al empezar a verificar un nombre distinto del verificado (`verifiedName !== name` y `verifyingName !== name`) se hace `state.verifiedName = null` ANTES de marcar `verifyingName = name`. Así `verifiedName` solo suprime re-consultas mientras el MISMO peleador sigue resuelto; volver a X con Y en vuelo dispara una nueva verificación de X (`verifyingName = X`, `verifySeq = seq`), la respuesta de Y se descarta por `verifyingName !== 'Y'` y la de X pinta el estado idle. `refreshFighter` ahora TAMBIÉN hace `state.verifiedName = null` al empezar (caso análogo detectado por Muad'Dib en autorevisión: refresh en vuelo + volver a escribir el mismo nombre → la verificación se saltaba y la respuesta tardía del refresh se descartaba por seq → sello en "Actualizando…"); al terminar sigue fijando `verifiedName = data.name` y `verifyingName = null`. `clearFighterUI` sigue limpiando `verifiedName`.

## Qué verificar
Recorré la máquina de estados con: (1) X ok → Y en vuelo → volver a X (el caso R2); (2) X ok → Y en vuelo → volver a X → Y responde tarde; (3) X en vuelo → Y en vuelo → X responde tarde; (4) X ok → editar texto sin cambiar de peleador resuelto (no debe re-consultar); (5) X ok → borrar input → volver a escribir X; (6) "Actualizar" con una verificación en vuelo; (7) "Actualizar" en vuelo → el usuario vuelve a escribir el mismo nombre (debe re-verificar y terminar idle). En cada caso: ¿el sello termina en idle/error coherente con el peleador mostrado y el botón habilitado? ¿alguna respuesta tardía pinta datos de otro peleador?

## Comandos
`node --check frontend/index.js`. (pytest no aplica a este cambio; Muad'Dib corrió la suite completa: 67 passed.) Sin internet, sin uvicorn, sin tocar `api/.env`.

## Formato
`SEVERIDAD — archivo:línea — qué falla, cómo reproducir, fix sugerido` (o "resuelto"). Cerrá con la línea exacta `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS`.
