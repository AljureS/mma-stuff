---
name: mma-ui-theme
description: Design system "Fight Night" para la UI del MMA Fight Predictor — paleta de corners rojo/azul, oro de campeonato, octágono, tale of the tape, tipografía y reglas de compatibilidad con index.js. Usa esta skill SIEMPRE que toques cualquier archivo de frontend/ o hables de diseño visual del proyecto: rediseñar la UI, cambiar colores, agregar componentes, "hazlo más MMA", "mejora el look", estilos, Tailwind, charts — incluso para cambios visuales pequeños, para que todo quede consistente con el tema.
---

# Design System "Fight Night"

La UI actual es un dashboard genérico gris/azul. El objetivo es que se sienta como una cartelera de pelea: oscura como una arena, con la tensión visual de dos corners enfrentados, y oro solo donde hay un título en juego. Cada decisión de diseño responde a esa metáfora — si un elemento no sabe de qué corner es, probablemente está mal diseñado.

## Conceptos rectores

1. **Corners, no "opciones A y B".** En MMA cada peleador tiene corner: rojo (retador/favorito local) y azul. TODO lo que compare a los dos peleadores usa este código de color de forma consistente: cards, chart, barras, texto del ganador. El usuario debe poder leer quién es quién solo por el color.
2. **Oro = campeonato.** El dorado se reserva exclusivamente para lo relacionado con título: el checkbox de title fight activo, el badge del cinturón, el glow del ganador en pelea titular. Si el oro aparece en un botón cualquiera, pierde su significado.
3. **La arena es oscura.** Fondos casi negros, la luz va sobre el contenido (como el octágono iluminado en un estadio a oscuras). Nada de fondos blancos.
4. **El octágono es el motivo geométrico.** Aparece en detalles: spinner de carga, clip de avatares, bordes de sección. Con moderación — un octágono por vista es tema; cinco es disfraz.

## Tokens

Definir en `tailwind.config` inline (el proyecto usa Tailwind por CDN — va en un `<script>` antes del contenido):

```html
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          arena:  { DEFAULT: '#0B0B0F', surface: '#14141B', raised: '#1D1D27', line: '#2A2A36' },
          corner: {
            red:  { DEFAULT: '#DC2626', hot: '#EF4444', deep: '#7F1D1D' },
            blue: { DEFAULT: '#2563EB', hot: '#3B82F6', deep: '#1E3A8A' },
          },
          gold:   { DEFAULT: '#D4AF37', bright: '#F0C948', deep: '#8B7020' },
          canvas: { DEFAULT: '#E7E5E4', muted: '#9CA3AF', faint: '#6B7280' },
        },
        fontFamily: {
          display: ['"Barlow Condensed"', 'Impact', 'sans-serif'],
          body: ['Inter', 'system-ui', 'sans-serif'],
        },
      },
    },
  }
</script>
```

Fuentes por Google Fonts CDN: **Barlow Condensed** (700/800, siempre `uppercase` + `tracking-wide`) para títulos, nombres de peleadores y números grandes — es la tipografía de póster de pelea. **Inter** para cuerpo y datos. No usar la display en párrafos: cansa.

## Componentes

**Fighter cards (corners).** Card izquierda = corner rojo, derecha = corner azul. Señal de corner: borde superior de 4px del color del corner + label "CORNER ROJO"/"CORNER AZUL" pequeño en display font. Fondo `arena-surface`, hover elevando a `arena-raised`.

**Bloque VS.** Entre las dos cards (centro del grid en desktop), un "VS" grande en display font con gradiente rojo→azul o blanco sobre octágono sutil. Es el punto focal del layout de entrada.

**Tale of the Tape.** Para comparaciones stat-a-stat (récord, alcance, edad...): tabla de tres columnas — valor rojo | nombre del stat centrado en `canvas-muted` uppercase | valor azul — con el valor superior de cada fila resaltado en su color de corner. Es EL formato canónico de comparación en MMA; preferirlo sobre cards sueltas cuando haya dos valores comparables.

**Probabilidades.** El doughnut de Chart.js se retematiza: `#DC2626` / `#2563EB` (corners), `borderColor: '#0B0B0F'`, leyenda en `canvas-muted`. Alternativa superior si se rediseña: una barra horizontal dividida (fight meter) — rojo desde la izquierda, azul desde la derecha, encuentro en el % — con los porcentajes en display font a cada extremo. Cualquiera de las dos, pero los colores de corner son obligatorios.

**Ganador.** Banner con el nombre en display font grande, fondo/glow del color de su corner. Si `title_fight`: glow dorado + icono de cinturón (`fa-belt` no existe en FA6 free — usar `fa-trophy` o `fa-crown`) y microcopy estilo "AND STILL / AND NEW".

**Title fight.** Checkbox activo = borde y check dorados + badge "TITLE FIGHT" en `gold`. Inactivo, sin rastro de oro.

**Spinner de carga.** Octágono girando: un div con `clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%)`, borde degradado rojo→azul, `animation: spin 1.2s linear infinite`. Texto tipo "ANALIZANDO LA PELEA..." en display font. Reemplaza al `.loading-spinner` circular actual.

**Key factors.** Cada factor con icono FA temático: alcance `fa-ruler-horizontal`, altura `fa-ruler-vertical`, striking `fa-hand-fist`, grappling/takedown `fa-user-ninja` (más seguro que `fa-people-arrows` en FA 6.0.0), experiencia `fa-clock-rotate-left`, edad `fa-cake-candles`, win rate `fa-chart-line`, cardio `fa-heart-pulse`, título `fa-trophy`. El color del texto/borde indica a qué corner favorece el factor. **Semántica del signo** (los `value` de la API son diffs A−B): positivo favorece al corner rojo (fighter_a), negativo al azul — EXCEPTO `age_difference` (positivo = A más viejo = favorece al azul; invertir) y `title_fight_factor` (no favorece a nadie → borde/icono oro, es campeonato).

**Análisis LLM.** Bloque tipo "análisis de esquina": borde izquierdo de 3px en gradiente rojo→azul, icono `fa-microphone` (comentarista), fondo `arena-surface`. El texto es contenido — legible, `canvas` sobre oscuro, `leading-relaxed`, nunca en display font.

## Reglas de compatibilidad (romper esto rompe la app)

- **Preservar TODOS los IDs que `index.js` referencia**: `fighterA`, `fighterB`, `weightClass`, `eventName`, `titleFight`, `predictBtn`, `probabilityChart`, `predictedWinner`, `winnerBanner`, `titleBeltNote`, `confidence`, `winProbability`, `keyFactors`, `llmAnalysis`, `resultsSection`, `loadingModal`, y los contenedores de stats por peleador (`fighter{A,B}Stats`, `fighter{A,B}Record`, `fighter{A,B}Ranking` — construidos con template literals). Desde 2026-09-26 también: `fighter{A,B}Suggestions` (`<ul>` de autocompletado, clases `.suggestions .suggestions-{red,blue}`), `fighter{A,B}Lookup` (fallback "Buscar en UFCStats": contiene `.lookup-row`, `.lookup-message` y `.lookup-btn[data-input=fighterA|fighterB]`), `errorBanner` + `errorMessage` (errores inline; ya no hay `alert()`). Desde 2026-09-26 (noche): `fighter{A,B}Freshness` (dentro de `fighter{A,B}Stats`: `.freshness-row` con `.freshness-message`, el icono en `.freshness-text i` y `.refresh-btn.refresh-btn-{red,blue}[data-input=fighterA|fighterB]` "Actualizar"; el JS alterna `.is-loading`/`.is-error` y deshabilita el botón mientras carga). Si el rediseño elimina una sección, eliminar su JS en el mismo cambio — nunca dejar `getElementById` huérfanos. (Nota refactor 2026-07: el backend eliminó `/events/upcoming`, `betting_insights` y `/analytics/*` — por tanto `marketOdds`/`bettingRecommendation`, la sección de betting, `displayBettingInsights` y `loadUpcomingEvents` deben eliminarse del frontend, NO preservarse. Ojo con la copia inline de index.js dentro de index.html: mientras exista, es la copia VIVA — el index.js externo muere en parse por redeclarar `const API_BASE_URL`. El rediseño debe eliminar el inline y dejar index.js como única fuente.)
- **El contrato con la API no cambia por diseño**: mismos endpoints, mismos payloads. El rediseño es capa de presentación.
- **`resultsSection` y `loadingModal` se muestran/ocultan vía la clase `hidden`** — mantener ese mecanismo.
- **Chart.js**: destruir la instancia previa antes de recrear (el código actual ya lo hace — conservarlo).
- **Idioma:** la UI está en español y se queda en español. Los términos de arte MMA (Tale of the Tape, VS, TITLE FIGHT) se quedan en inglés — así se usan en el deporte, incluso en transmisiones en español.
- **Clases que inyecta JS en runtime → `styles.css`, no utilidades Tailwind.** El Play CDN genera utilidades observando el DOM; una clase custom del config (p. ej. `text-corner-red-hot`) que SOLO aparece vía `innerHTML`/`classList.add` depende del MutationObserver y puede parpadear o fallar. Las clases dinámicas del rediseño 2026-07 son semánticas y viven en `styles.css`: `.winner-red/.winner-blue`, `.winner-glow-{red,blue,gold}` (banner), `.factor-item` + `.factor-{red,blue,gold}` (key factors). Mantener ese patrón para todo lo que pinte el JS.
- **El estado de title fight no viene en la respuesta de `/predict`** (el response model no lo incluye); el JS lo toma del request/checkbox `titleFight` al momento de pintar el banner (glow dorado + nota de cinturón `titleBeltNote`).

## Accesibilidad y sobriedad

- Contraste: texto principal `#E7E5E4` sobre `#0B0B0F` pasa AAA; `canvas-muted` (#9CA3AF) solo para labels, nunca para datos críticos.
- `focus:ring-2` visible en inputs sobre fondo oscuro (ring del color del corner correspondiente).
- Los porcentajes y nombres de ganador nunca dependen SOLO del color para entenderse (siempre etiquetados con texto).
- Resistir el impulso de agregar sangre, llamas o texturas grunge: la estética de UFC moderna es limpia y tipográfica. El drama lo ponen el contraste, la tipografía condensada y los dos colores de corner.
