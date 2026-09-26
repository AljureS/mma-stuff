---
name: refactor-verify
description: Checklist de verificación (definición de "terminado") para cambios del MMA Fight Predictor — paridad con baseline, tests, stack vivo y docs sincronizadas. Usa esta skill SIEMPRE antes de marcar como completa cualquier tarea de refactor, dar un cambio por terminado, decir "listo/done/funciona", cerrar una fase de tasks/todo.md, o cuando el usuario pregunte "¿ya quedó?" o "¿no se rompió nada?". Nunca declares terminado un cambio sin correr esto.
---

# Verificación de refactor: definición de "terminado"

"Los tests pasan" no es suficiente en este proyecto: los 15 tests cubren SOLO `api/llm_client.py`. `main.py`, el scraper y el frontend no tienen tests — su única verificación es ejecutarlos de verdad. Por eso el checklist mezcla tests, ejecución real y paridad con baseline.

## Paso 0 — Baseline (ANTES de cambiar nada)

Si vas a empezar un cambio y no existe baseline fresco, captúralo primero (stack arriba según skill `mma-run-stack`):

```bash
mkdir -p tasks/baselines
curl -s http://localhost:8000/ > tasks/baselines/health.json
curl -s "http://localhost:8000/search/fighters/jon" > tasks/baselines/search.json
curl -s -X POST http://localhost:8000/predict -H "Content-Type: application/json" \
  -d '{"fighter_a": "Jon Jones", "fighter_b": "Stipe Miocic", "include_llm_analysis": false}' \
  > tasks/baselines/predict.json
```

El baseline de `/predict` es oro: el modelo actual es determinístico para el mismo input, así que **la probabilidad debe ser idéntica antes y después** de cualquier cambio que no toque features ni modelo. Si cambió, rompiste el pipeline aunque nada lance excepción. (Excepción legítima: el auto-scraping actualizó el CSV del peleador — verifica `last_updated` antes de culpar a tu cambio.)

## Checklist (todos, en orden)

1. **Tests unitarios:**
   ```bash
   venv/bin/python -m pytest tests/ -v
   ```
   15/15 verdes. Si borraste código, cero tests nuevos rotos por imports.

2. **La API arranca limpia.** Reiniciar el proceso (no confíes en un proceso viejo con código viejo en memoria) y revisar el log de startup: modelo cargado, N peleadores, sin tracebacks.

3. **Paridad con baseline.** Repetir los 3 curls del paso 0 y comparar contra `tasks/baselines/`:
   - `/predict`: misma probabilidad (ver excepción arriba), misma estructura de respuesta.
   - `/`: `models_loaded: true`, `fighters_count` igual o mayor.
   - Endpoints borrados a propósito: deben dar 404 — y NO deben seguir en el frontend ni en CLAUDE.md.

4. **Frontend smoke.** Servir `frontend/` (`:3000`) y verificar: la página carga sin 404s de assets, una predicción end-to-end desde la UI muestra resultados, y no hay errores en consola del navegador — como mínimo, greppear que todo `getElementById('X')` de index.js tenga su `id="X"` en index.html:
   ```bash
   for id in $(grep -o "getElementById('[^']*')" frontend/index.js | sed "s/.*('\(.*\)')/\1/" | sort -u); do
     grep -q "id=\"$id\"" frontend/index.html || echo "HUÉRFANO: $id"
   done
   ```

5. **Docs sincronizadas.** CLAUDE.md refleja el cambio (skill `sync-claude-md`). Si borraste algo, ya no aparece como existente en ningún doc (`grep -ri <nombre> *.md`).

6. **Diff review.** `git diff` completo del cambio: ¿solo tocaste lo necesario? ¿algún archivo modificado por accidente? (`data/fighters_complete.csv` modificado es normal — la API escribe en runtime; no lo revientes ni lo commitees como parte de un cambio de código sin mencionarlo.)

7. **La pregunta final:** ¿un staff engineer aprobaría esto? Si la respuesta necesita un "bueno, es que..." — no está terminado.

## Al terminar

- Marca el item en `tasks/todo.md` y anota el resultado en su sección Review (qué se verificó, qué salió).
- Si el usuario corrigió algo durante el cambio → registra el patrón en `tasks/lessons.md`.
- Reporta resultados con evidencia (salidas reales), no con adjetivos: "pytest 15/15, predict 0.6656 == baseline" y no "todo funciona perfecto".
