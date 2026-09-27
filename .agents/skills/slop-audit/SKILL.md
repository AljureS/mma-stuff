---
name: slop-audit
description: Procedimiento basado en evidencia para identificar y eliminar código muerto, placeholders y dependencias sin uso en el MMA Fight Predictor sin romper nada. Usa esta skill SIEMPRE antes de borrar cualquier archivo, función, endpoint, import o dependencia, y cuando el usuario pida "limpiar", "borrar código muerto", "quitar slop", "esto se usa?", "dead code" o "simplificar el proyecto" — incluso si el borrado parece obvio.
---

# Auditoría de slop: borrar sin romper

Borrar código es la operación más fácil de hacer mal: el costo de un falso positivo (borrar algo vivo) es una API rota en runtime, y el de un falso negativo es solo un poco más de ruido. Por eso el veredicto BORRABLE exige evidencia, no intuición.

## Estándar de evidencia (los 4 checks)

Un item es **BORRABLE** solo si pasa los 4:

1. **Cero referencias estáticas.** Grep repo-wide por el nombre del símbolo Y por el nombre del módulo/archivo — en `.py`, `.js`, `.html`, `.sh`, `.md`, configs. Excluye `venv/` y `.git/`. Una referencia solo en docs no lo salva (se corrige la doc), pero hay que saberlo antes.
2. **Cero referencias dinámicas.** Este repo tiene trampas (ver abajo): imports vía `sys.path`, strings que nombran módulos, JS que llama endpoints por URL. Grep también por el nombre como string (`"nombre"`, `'nombre'`) y por rutas de endpoint (`/retrain`, `/analytics`).
3. **Cadena de llamadas completa.** "Nadie lo llama" ≠ "solo lo llama código que a su vez está muerto". Distingue: llamado por producción / solo por script manual / solo por un `main()` inaccesible / por nadie. Los dos últimos son borrables; el segundo requiere decidir si el script manual se conserva.
4. **Verificación post-borrado.** Después de borrar: `venv/bin/python -m pytest tests/ -v` + arrancar la API + smoke de `/predict` (ver skill `mma-run-stack`). Un borrado sin verificación no está terminado.

## Procedimiento

1. Corre los greps de los checks 1–3 y arma la tabla de veredicto: `item | veredicto | quién lo referencia | evidencia file:line`.
2. Borra en commits/cambios atómicos: un concepto por cambio (p. ej. "ml_system.py fuera" separado de "deps fuera de requirements"). Si algo se rompe, el bisect es trivial.
3. Cuando borres un endpoint, borra en el MISMO cambio su consumidor en `frontend/index.js` y su sección en `index.html` — y viceversa.
4. Cuando borres un import/dependencia de `requirements.txt`, reinstala en el venv y arranca la API para confirmar que no era dependencia implícita de otra cosa.
5. Actualiza `AGENTS.md` (skill `sync-Codex-md`) y marca el item en `tasks/todo.md`. Un borrado que la doc sigue afirmando que existe es drift instantáneo.

## Trampas conocidas de ESTE repo (aprendidas en la auditoría 2026-07-01)

- **Import dinámico vía sys.path:** `api/main.py` agrega `scripts/` al `sys.path` para importar `data_collection`. Un grep ingenuo por `from scripts.data_collection` da cero resultados y te haría creer que el módulo está muerto. Grep por `data_collection` a secas.
- **JS duplicado inline:** `frontend/index.html` contiene una copia íntegra de `index.js` inline ADEMÁS de cargar el archivo externo. Hasta que se elimine el duplicado, cualquier análisis (o edición) del frontend tiene que revisar AMBAS copias.
- **Cadenas internas del scraper:** `get_fighter_detailed_stats()` parece muerto si solo miras llamadas externas, pero verifica si `search_and_scrape_fighter()` lo llama internamente (y de él dependen `_normalize_stat_name`/`_parse_stat_value`). Las auditorías previas se contradijeron aquí — resolver con lectura directa del código, no con grep.
- **El vector de 16 features es contrato con el pkl:** el modelo XGBoost espera exactamente 16 inputs. El relleno con ceros en `engineer_fight_features()` es feo pero NO es slop borrable — quitarlo rompe `/predict`. Se documenta, no se borra (hasta reentrenar).
- **La convención `probabilities[1]` = probabilidad de fighter_a.** Cualquier refactor de `/predict` debe preservarla o el ganador se invierte silenciosamente.
- **El CSV se escribe en runtime:** `data/fighters_complete.csv` es base de datos viva, no fixture. Jamás tratarlo como artefacto regenerable sin pérdida.

## Qué es placeholder vs qué es slop

No todo placeholder se borra igual. Tres categorías con destinos distintos:

- **Mentiras al usuario** (endpoints que devuelven datos inventados como reales: `/analytics/*`, odds fijas): borrar el endpoint, o si se decide conservar la superficie, hacer que falle explícito (`501 Not Implemented`). Nunca dejar datos falsos que parecen reales.
- **Esqueletos honestos** (código con `YOUR_API_KEY`, cuerpos comentados): borrar — git recuerda todo; recuperarlo cuesta un `git log` si algún día se implementa de verdad.
- **Deuda documentada que funciona** (padding de features, defaults del scraper): NO borrar; están en AGENTS.md como trabajo pendiente y el sistema depende de ellos hoy.

El inventario concreto y actualizado de qué borrar en este refactor vive en `tasks/todo.md` — esta skill define el cómo; el todo define el qué.
