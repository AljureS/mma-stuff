# Brief (HalJordan): confirmación acotada tras R3 — una línea en `refreshFighter` (solo lectura)

Tu R3 (registro 20260927T024809Z) dio NO BLOCKERS. Después de ese veredicto Muad'Dib aplicó UNA línea más en `frontend/index.js`, `refreshFighter`: `state.verifiedName = null;` justo después de `const seq = ++state.seq;` (con comentario). Motivo: refresh en vuelo + el usuario vuelve a escribir el MISMO nombre → `searchFighter` resolvía el nombre, `verifyFighterFreshness` lo saltaba por `verifiedName === name`, la respuesta tardía del refresh se descartaba por `seq` y el sello quedaba en "Actualizando…" con el botón deshabilitado (mismo patrón que tu HIGH de R2).

NO edites nada. Confirmá SOLO: (a) que esa línea corrige el escenario descrito (refresh en vuelo → reescribir el mismo nombre → debe correr una verificación y terminar idle), (b) que no rompe los escenarios que ya diste por resueltos en R3 (X ok → Y en vuelo → volver a X; ediciones sin cambiar de peleador; borrar y reescribir; "Actualizar" con verificación en vuelo), y (c) `node --check frontend/index.js`.

Formato: una línea por escenario ("resuelto"/hallazgo con severidad y archivo:línea) y cerrá con la línea exacta `VERDICT: NO BLOCKERS` o `VERDICT: BLOCKERS`.
