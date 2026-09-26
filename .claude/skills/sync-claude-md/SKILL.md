---
name: sync-claude-md
description: Procedimiento para mantener CLAUDE.md como fuente única de verdad del MMA Fight Predictor después de cualquier cambio al proyecto. Usa esta skill SIEMPRE que modifiques, agregues o borres código, endpoints, archivos, dependencias, estructura o configuración — al FINAL de cada cambio, sin excepción y sin que te lo pidan; también cuando el usuario diga "actualiza la doc", "sincroniza el CLAUDE.md" o notes drift entre doc y código.
---

# Sincronizar CLAUDE.md

La regla número uno de este repo (está en el banner del propio CLAUDE.md): **cualquier cambio al proyecto debe reflejarse inmediatamente en CLAUDE.md**. La razón: este proyecto ya sufrió drift grave — docs que referenciaban archivos inexistentes (`mma_frontend.html`, `training_data.csv`) costaron horas de confusión. CLAUDE.md es lo único que las sesiones futuras cargan siempre; si miente, todo lo demás se decide mal.

## El principio editorial

CLAUDE.md describe el estado **REAL** del código y distingue explícitamente **implementado** vs **placeholder/simulado**. Al actualizar:

- Nunca describas una intención como si fuera realidad ("la API usa PostgreSQL" cuando hay un schema sin conectar).
- Si algo es placeholder/dummy/hardcodeado, dilo con esas palabras.
- Si borras algo, bórralo de la doc — no lo dejes como "deprecated".
- Convierte fechas relativas en absolutas ("actualmente" → "a 2026-07-01").

## Mapa: tipo de cambio → secciones a tocar

| Cambiaste... | Actualiza en CLAUDE.md |
|---|---|
| Endpoint (nuevo/borrado/comportamiento) | Tabla "Endpoints" + "Flujo de /predict" si aplica + "Estado Actual" |
| Archivo creado/borrado/movido | Árbol de "Estructura Real del Proyecto" (con su comentario de una línea) |
| Dependencia en requirements.txt | "Stack Tecnológico" + sección del componente afectado |
| Variable de entorno | "Variables de Entorno" (distinguir leídas vs no leídas por el código) |
| Features/modelo/pipeline ML | "Features del modelo" + "Estado Actual" |
| Cliente LLM | "Componente 2" (flujo, timeouts, breakers, costos) |
| Scraper | "Componente 3" + defaults si cambiaron |
| Frontend | "Componente 4" (+ skill `mma-ui-theme` si cambió el design system) |
| Bug conocido arreglado | Quitarlo de "Bugs conocidos" y de "Trabajo Pendiente" |
| Algo placeholder implementado de verdad | Moverlo de la lista "Placeholder/simulado" a "Implementado y funcional" |
| Cómo se corre/testea | "Cómo Ejecutar" / "Tests" |

Regla práctica: después de editar, grep en CLAUDE.md por el nombre de todo lo que tocaste (`grep -n <nombre> CLAUDE.md`) — cada mención debe seguir siendo cierta.

## Además de CLAUDE.md

1. **`tasks/todo.md`**: marca el checkbox del item ejecutado y agrega una línea a la sección Review (qué se hizo, resultado de verificación).
2. **`tasks/lessons.md`**: solo si hubo corrección del usuario en el camino — registra patrón + regla preventiva.
3. **Otros docs** (README.md, README_LLM.md): si tu cambio los vuelve mentirosos, corrígelos o marca el drift en todo.md. No dupliques contenido nuevo en ellos — el detalle vive en CLAUDE.md y los README apuntan ahí.

## Anti-patrones (no hacer)

- Actualizar la doc "al final del día" en batch: se olvida. Es parte del mismo cambio, mismo commit.
- Agregar secciones nuevas a CLAUDE.md cuando una existente ya cubre el tema: el archivo crece y deja de leerse. Edita en el lugar correcto.
- Documentar en CLAUDE.md lo que git ya registra (quién cambió qué y cuándo) o detalles de implementación evidentes leyendo el código. CLAUDE.md guarda lo que NO es obvio: estado real vs aparente, contratos frágiles, decisiones.
