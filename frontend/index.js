// Configuration
const API_BASE_URL = window.location.protocol === 'file:' || window.location.port === '3000'
    ? 'http://localhost:8000'
    : window.location.origin;

// State
let currentPrediction = null;
let probabilityChart = null;

// Estado de búsqueda POR corner: timer de debounce, número de secuencia (para ignorar
// respuestas que llegan fuera de orden) y sugerencias visibles. Antes había un solo
// timer compartido: escribir en el corner azul cancelaba la búsqueda del rojo, y una
// respuesta lenta podía pisar a una más nueva.
// verifiedName: nombre canónico ya verificado con GET /fighter y aún resuelto (no repetir la llamada por tecla;
// se invalida en cuanto empieza la verificación de OTRO peleador);
// verifyingName/verifySeq: verificación EN VUELO y la secuencia que la espera (si el usuario vuelve al
// mismo nombre antes de la respuesta, se adopta la llamada en curso en vez de saltarla o duplicarla).
const searchState = {
    fighterA: { timer: null, seq: 0, suggestions: [], activeIndex: -1, verifiedName: null, verifyingName: null, verifySeq: 0 },
    fighterB: { timer: null, seq: 0, suggestions: [], activeIndex: -1, verifiedName: null, verifyingName: null, verifySeq: 0 }
};
const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_LIMIT = 8;

// Corner colors (design system Fight Night — deben coincidir con tailwind.config de index.html)
const CORNER_RED = '#DC2626';
const CORNER_BLUE = '#2563EB';
const ARENA_BG = '#0B0B0F';
const CANVAS_MUTED = '#9CA3AF';

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    initializeEventListeners();
});

function initializeEventListeners() {
    // Predict button
    document.getElementById('predictBtn').addEventListener('click', makePrediction);

    // Fighter inputs: búsqueda con debounce independiente por corner + navegación con teclado
    ['fighterA', 'fighterB'].forEach(id => {
        const input = document.getElementById(id);
        const state = searchState[id];

        input.addEventListener('input', function (e) {
            clearTimeout(state.timer);
            state.seq++; // cada tecla invalida al instante toda búsqueda o lookup en vuelo
            hideError();
            const query = e.target.value.trim();
            if (query.length < 2) {
                clearFighterUI(id);
                return;
            }
            state.timer = setTimeout(() => searchFighter(id, query), SEARCH_DEBOUNCE_MS);
        });

        input.addEventListener('keydown', function (e) {
            handleSuggestionKeys(id, e);
        });

        input.addEventListener('focus', function () {
            if (state.suggestions.length > 0) showSuggestions(id);
        });

        // Pequeño retraso: si el usuario hace click en una sugerencia, el click llega antes de ocultar
        input.addEventListener('blur', function () {
            setTimeout(() => hideSuggestions(id), 150);
        });
    });

    // Botones "Buscar en UFCStats" (fallback cuando la base local no tiene al peleador)
    document.querySelectorAll('.lookup-btn').forEach(btn => {
        btn.addEventListener('click', () => lookupFighterOnUfcStats(btn.dataset.input));
    });

    // Botones "Actualizar": re-scrape forzado del perfil en UFCStats (GET /fighter/{name}?refresh=true)
    document.querySelectorAll('.refresh-btn').forEach(btn => {
        btn.addEventListener('click', () => refreshFighter(btn.dataset.input));
    });
}

async function searchFighter(inputId, query) {
    const state = searchState[inputId];
    const seq = ++state.seq;

    try {
        const response = await fetch(`${API_BASE_URL}/search/fighters/${encodeURIComponent(query)}?limit=${SEARCH_LIMIT}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        // Llegó tarde: ya hay una búsqueda más nueva para este corner
        if (seq !== state.seq) return;

        const results = data.results || [];
        if (results.length === 0) {
            clearSuggestions(inputId);
            hideFighterStats(inputId);
            setLookupState(inputId, 'idle', 'No está en la base local.');
            return;
        }

        hideLookup(inputId);
        renderSuggestions(inputId, results);

        // Mostrar el récord solo si no hay ambigüedad: match exacto o un único resultado
        const exact = results.find(f => f.name.toLowerCase() === query.toLowerCase());
        const resolved = exact || (results.length === 1 ? results[0] : null);
        if (resolved) {
            updateFighterStats(inputId, resolved);
            verifyFighterFreshness(inputId, resolved.name, seq);
        } else {
            hideFighterStats(inputId);
        }
    } catch (error) {
        console.error('Error searching fighter:', error);
        if (seq === state.seq) {
            clearSuggestions(inputId);
            hideFighterStats(inputId);
            setLookupState(inputId, 'error', 'No se pudo consultar la base local. Intenta de nuevo.');
        }
    }
}

function renderSuggestions(inputId, results) {
    const state = searchState[inputId];
    const list = document.getElementById(`${inputId}Suggestions`);
    state.suggestions = results;
    state.activeIndex = -1;
    list.innerHTML = '';

    results.forEach((fighter, index) => {
        const item = document.createElement('li');
        item.className = 'suggestion-item';
        item.setAttribute('role', 'option');

        const name = document.createElement('span');
        name.className = 'suggestion-name';
        name.textContent = fighter.name;

        const meta = document.createElement('span');
        meta.className = 'suggestion-meta';
        meta.textContent = [fighter.record, formatWeightClass(fighter.weight_class)].filter(Boolean).join(' · ');

        item.append(name, meta);
        // mousedown con preventDefault: el input no pierde el foco antes de que llegue el click
        item.addEventListener('mousedown', e => e.preventDefault());
        item.addEventListener('click', () => selectSuggestion(inputId, index));
        list.appendChild(item);
    });

    showSuggestions(inputId);
}

function selectSuggestion(inputId, index) {
    const state = searchState[inputId];
    const fighter = state.suggestions[index];
    if (!fighter) return;

    state.seq++; // el usuario ya eligió: descartar búsquedas en vuelo
    clearTimeout(state.timer);
    document.getElementById(inputId).value = fighter.name; // nombre canónico del CSV
    updateFighterStats(inputId, fighter);
    verifyFighterFreshness(inputId, fighter.name, state.seq);
    hideSuggestions(inputId);
    hideLookup(inputId);
}

function handleSuggestionKeys(inputId, e) {
    const state = searchState[inputId];
    const list = document.getElementById(`${inputId}Suggestions`);
    const open = !list.classList.contains('hidden') && state.suggestions.length > 0;

    if (e.key === 'Escape') {
        hideSuggestions(inputId);
        return;
    }
    if (!open) return;

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const delta = e.key === 'ArrowDown' ? 1 : -1;
        const count = state.suggestions.length;
        state.activeIndex = (state.activeIndex + delta + count) % count;
        list.querySelectorAll('.suggestion-item').forEach((item, i) => {
            item.classList.toggle('is-active', i === state.activeIndex);
        });
    } else if (e.key === 'Enter' && state.activeIndex >= 0) {
        e.preventDefault();
        selectSuggestion(inputId, state.activeIndex);
    }
}

function showSuggestions(inputId) {
    document.getElementById(`${inputId}Suggestions`).classList.remove('hidden');
    document.getElementById(inputId).setAttribute('aria-expanded', 'true');
}

function hideSuggestions(inputId) {
    const list = document.getElementById(`${inputId}Suggestions`);
    list.classList.add('hidden');
    searchState[inputId].activeIndex = -1;
    list.querySelectorAll('.is-active').forEach(item => item.classList.remove('is-active'));
    document.getElementById(inputId).setAttribute('aria-expanded', 'false');
}

function formatWeightClass(weightClass) {
    if (!weightClass || String(weightClass).toLowerCase() === 'unknown') return '';
    return String(weightClass).replace(/_/g, ' ');
}

function updateFighterStats(inputId, fighter) {
    const letter = inputId === 'fighterA' ? 'A' : 'B';
    const statsDiv = document.getElementById(`fighter${letter}Stats`);
    const recordSpan = document.getElementById(`fighter${letter}Record`);
    const rankingSpan = document.getElementById(`fighter${letter}Ranking`);

    recordSpan.textContent = fighter.record || '-';
    rankingSpan.textContent = fighter.ranking ? `#${fighter.ranking}` : 'NR';

    statsDiv.classList.remove('hidden');
}

function hideFighterStats(inputId) {
    const letter = inputId === 'fighterA' ? 'A' : 'B';
    document.getElementById(`fighter${letter}Stats`).classList.add('hidden');
}

function clearSuggestions(inputId) {
    searchState[inputId].suggestions = [];
    document.getElementById(`${inputId}Suggestions`).innerHTML = '';
    hideSuggestions(inputId);
}

function clearFighterUI(inputId) {
    searchState[inputId].verifiedName = null;
    clearSuggestions(inputId);
    hideFighterStats(inputId);
    hideLookup(inputId);
}

// Fallback cuando la base local no tiene al peleador: GET /fighter/{name} dispara el
// scraping de UFCStats en el backend (tarda unos segundos) y lo agrega al CSV.
async function lookupFighterOnUfcStats(inputId) {
    const input = document.getElementById(inputId);
    const query = input.value.trim();
    if (query.length < 2) return;

    const state = searchState[inputId];
    const seq = ++state.seq; // invalida búsquedas locales en vuelo
    clearTimeout(state.timer);
    hideSuggestions(inputId);
    setLookupState(inputId, 'loading', 'Buscando en UFCStats…');

    try {
        const response = await fetch(`${API_BASE_URL}/fighter/${encodeURIComponent(query)}`);
        if (seq !== state.seq) return;

        if (response.status === 404) {
            hideFighterStats(inputId);
            setLookupState(inputId, 'notfound', 'No encontrado en UFCStats. Prueba con el nombre completo.');
            return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        if (seq !== state.seq) return; // el usuario siguió escribiendo mientras respondía UFCStats
        input.value = data.name; // nombre canónico de UFCStats
        state.verifiedName = data.name; // esta respuesta ya pasó por las reglas de frescura
        applyFighterResponse(inputId, data);
        hideLookup(inputId);
    } catch (error) {
        console.error('Error looking up fighter on UFCStats:', error);
        if (seq === state.seq) {
            setLookupState(inputId, 'error', 'No se pudo consultar UFCStats. Intenta de nuevo.');
        }
    }
}

function setLookupState(inputId, mode, message) {
    const container = document.getElementById(`${inputId}Lookup`);
    const row = container.querySelector('.lookup-row');
    const text = container.querySelector('.lookup-message');
    const icon = container.querySelector('.lookup-text i');
    const button = container.querySelector('.lookup-btn');

    row.classList.remove('is-loading', 'is-notfound', 'is-error');
    if (mode !== 'idle') row.classList.add(`is-${mode}`);
    text.textContent = message;
    icon.className = mode === 'loading' ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-circle-info';
    button.disabled = mode === 'loading';
    container.classList.remove('hidden');
}

function hideLookup(inputId) {
    const container = document.getElementById(`${inputId}Lookup`);
    container.classList.add('hidden');
    container.querySelector('.lookup-btn').disabled = false;
}

// --- Frescura de datos por corner ---
// GET /fighter/{name} aplica las reglas de frescura del backend (re-scrapea si los datos superan
// FIGHTER_MAX_AGE_HOURS o si el peleador peleó desde la última lectura) y devuelve el sello
// last_updated / data_age_seconds / next_fight_date. Se llama al resolver un peleador; con
// ?refresh=true (botón "Actualizar") fuerza el re-scrape aunque los datos sean recientes.
async function verifyFighterFreshness(inputId, name, seq) {
    const state = searchState[inputId];
    if (state.verifiedName === name) return; // ya verificado y sigue siendo el peleador mostrado
    if (state.verifyingName === name) {
        state.verifySeq = seq; // ya hay una llamada en vuelo para este nombre: que su respuesta valga para esta secuencia
        return;
    }
    // Cambió el peleador resuelto: lo verificado antes ya no describe lo que se muestra. Si el usuario
    // vuelve a aquel nombre, se vuelve a consultar (ms si está fresco) en vez de reutilizar un estado
    // que la verificación en vuelo de otro peleador pudo haber pisado (review HalJordan R2).
    state.verifiedName = null;
    state.verifyingName = name;
    state.verifySeq = seq;
    setFreshnessState(inputId, 'loading', 'Verificando datos en UFCStats…');

    let data;
    try {
        data = await fetchFighter(name, false);
    } catch (error) {
        console.error('Error verifying fighter data:', error);
        if (state.verifyingName !== name) return; // la reemplazó otra verificación
        state.verifyingName = null;
        if (state.verifySeq === state.seq) {
            setFreshnessState(inputId, 'error', 'No se pudo verificar la frescura de los datos.');
        }
        return;
    }
    if (state.verifyingName !== name) return; // la reemplazó otra verificación (otro peleador)
    state.verifyingName = null;
    if (state.verifySeq !== state.seq) return; // el usuario cambió o borró el peleador mientras tanto
    state.verifiedName = name;
    applyFighterResponse(inputId, data);
}

async function refreshFighter(inputId) {
    const input = document.getElementById(inputId);
    const name = input.value.trim();
    if (name.length < 2) return;

    const state = searchState[inputId];
    const seq = ++state.seq; // descarta búsquedas y verificaciones en vuelo
    // El refresh reemplaza a cualquier verificación previa: si el usuario vuelve a escribir este mismo
    // nombre mientras el refresh está en vuelo, la verificación debe correr (y no quedarse en "Actualizando…").
    state.verifiedName = null;
    clearTimeout(state.timer);
    hideSuggestions(inputId);
    hideError();
    setFreshnessState(inputId, 'loading', 'Actualizando desde UFCStats…');

    try {
        const data = await fetchFighter(name, true);
        if (seq !== state.seq) return;
        input.value = data.name; // nombre canónico de UFCStats
        state.verifiedName = data.name;
        state.verifyingName = null; // una verificación en vuelo para este nombre ya no debe pintar nada
        applyFighterResponse(inputId, data);
    } catch (error) {
        console.error('Error refreshing fighter:', error);
        if (seq === state.seq) {
            setFreshnessState(inputId, 'error', error.status === 404
                ? 'No encontrado en UFCStats. Prueba con el nombre completo.'
                : 'No se pudo actualizar desde UFCStats. Intenta de nuevo.');
        }
    }
}

async function fetchFighter(name, refresh) {
    const suffix = refresh ? '?refresh=true' : '';
    const response = await fetch(`${API_BASE_URL}/fighter/${encodeURIComponent(name)}${suffix}`);
    if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

// Traduce la respuesta de GET /fighter al objeto que pinta updateFighterStats
function applyFighterResponse(inputId, data) {
    const stats = data.stats || {};
    const fighter = {
        name: data.name,
        record: data.record,
        ranking: data.ranking,
        weight_class: stats.weight_class,
        last_updated: data.last_updated ?? stats.last_updated ?? null,
        next_fight_date: data.next_fight_date ?? stats.next_fight_date ?? null,
        data_age_seconds: data.data_age_seconds ?? null
    };
    updateFighterStats(inputId, fighter);
    // Toda respuesta exitosa de /fighter cierra el estado de carga, aunque no traiga sello de edad
    setFreshnessState(inputId, 'idle', describeFreshness(fighter));
}

function describeFreshness(fighter) {
    const age = formatDataAge(fighter.data_age_seconds, fighter.last_updated);
    let text = age ? `Datos de UFCStats: ${age}` : 'Datos de UFCStats';

    if (fighter.next_fight_date) {
        const today = localIsoDate(new Date());
        if (fighter.next_fight_date === today) {
            text += ' · pelea hoy (actualiza al terminar)';
        } else if (fighter.next_fight_date > today) {
            text += ` · próxima pelea ${formatShortDate(fighter.next_fight_date)}`;
        } else {
            text += ` · peleó el ${formatShortDate(fighter.next_fight_date)}`;
        }
    }
    return text;
}

// Edad de los datos: el backend la calcula (data_age_seconds) para no depender de la zona
// horaria del servidor; last_updated (ISO sin zona) queda como fallback.
function formatDataAge(ageSeconds, lastUpdated) {
    let seconds = typeof ageSeconds === 'number' ? ageSeconds : NaN;
    if (!Number.isFinite(seconds) && lastUpdated) {
        const parsed = Date.parse(String(lastUpdated).replace(/(\.\d{3})\d+/, '$1'));
        if (!Number.isNaN(parsed)) seconds = (Date.now() - parsed) / 1000;
    }
    if (!Number.isFinite(seconds)) return null;
    seconds = Math.max(0, seconds);
    if (seconds < 60) return 'hace un momento';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `hace ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `hace ${hours} h`;
    const days = Math.floor(hours / 24);
    return `hace ${days} ${days === 1 ? 'día' : 'días'}`;
}

function localIsoDate(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatShortDate(isoDate) {
    const date = new Date(`${isoDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) return isoDate;
    return date.toLocaleDateString('es', { day: 'numeric', month: 'short' });
}

function setFreshnessState(inputId, mode, message) {
    const letter = inputId === 'fighterA' ? 'A' : 'B';
    const row = document.getElementById(`fighter${letter}Freshness`);
    const text = row.querySelector('.freshness-message');
    const icon = row.querySelector('.freshness-text i');
    const button = row.querySelector('.refresh-btn');

    row.classList.remove('is-loading', 'is-error');
    if (mode !== 'idle') row.classList.add(`is-${mode}`);
    text.textContent = message;
    icon.className = mode === 'loading' ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-clock-rotate-left';
    button.disabled = mode === 'loading';
}

function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorBanner').classList.remove('hidden');
}

function hideError() {
    document.getElementById('errorBanner').classList.add('hidden');
}

async function makePrediction() {
    const fighterA = document.getElementById('fighterA').value.trim();
    const fighterB = document.getElementById('fighterB').value.trim();

    hideError();

    if (!fighterA || !fighterB) {
        showError('Por favor ingresa ambos luchadores.');
        return;
    }

    if (fighterA.toLowerCase() === fighterB.toLowerCase()) {
        showError('Los luchadores deben ser diferentes.');
        return;
    }

    showLoading(true);

    try {
        const requestData = {
            fighter_a: fighterA,
            fighter_b: fighterB,
            event_name: document.getElementById('eventName').value,
            weight_class: document.getElementById('weightClass').value,
            title_fight: document.getElementById('titleFight').checked,
            include_llm_analysis: true
        };

        const response = await fetch(`${API_BASE_URL}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const detail = errorData.detail || 'Error making prediction';
            if (response.status === 404) {
                const match = /not found in database: (.+?)\. /.exec(detail);
                const who = match ? match[1] : 'uno de los peleadores';
                throw new Error(`No se encontró a ${who} en la base local ni en UFCStats. Revisa el nombre completo o usa "Buscar en UFCStats".`);
            }
            throw new Error(detail);
        }

        const prediction = await response.json();
        currentPrediction = prediction;

        displayPredictionResults(prediction, requestData.title_fight);

    } catch (error) {
        console.error('Error making prediction:', error);
        showError(error.message);
    } finally {
        showLoading(false);
    }
}

function displayPredictionResults(prediction, titleFight) {
    // Show results section
    document.getElementById('resultsSection').classList.remove('hidden');

    // Winner banner (glow del corner del ganador; dorado si es pelea titular)
    displayWinnerBanner(prediction, titleFight);

    // Update summary numbers
    document.getElementById('confidence').textContent = `${(prediction.confidence * 100).toFixed(1)}%`;

    const winnerProb = prediction.predicted_winner === prediction.fighter_a ?
        prediction.probability_a_wins : prediction.probability_b_wins;
    document.getElementById('winProbability').textContent = `${(winnerProb * 100).toFixed(1)}%`;

    // Update chart
    updateProbabilityChart(prediction);

    // Update key factors
    displayKeyFactors(prediction.key_factors, prediction);

    // Update AI analysis
    document.getElementById('llmAnalysis').textContent =
        prediction.llm_analysis || 'Análisis no disponible';

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function displayWinnerBanner(prediction, titleFight) {
    const banner = document.getElementById('winnerBanner');
    const winnerEl = document.getElementById('predictedWinner');
    const beltNote = document.getElementById('titleBeltNote');
    const winnerIsRed = prediction.predicted_winner === prediction.fighter_a;

    // Limpiar estado de una predicción anterior
    banner.classList.remove('winner-glow-red', 'winner-glow-blue', 'winner-glow-gold');
    winnerEl.classList.remove('winner-red', 'winner-blue');

    winnerEl.textContent = prediction.predicted_winner;
    winnerEl.classList.add(winnerIsRed ? 'winner-red' : 'winner-blue');
    banner.classList.add(titleFight ? 'winner-glow-gold' : (winnerIsRed ? 'winner-glow-red' : 'winner-glow-blue'));
    beltNote.classList.toggle('hidden', !titleFight);
}

function updateProbabilityChart(prediction) {
    const ctx = document.getElementById('probabilityChart').getContext('2d');

    if (probabilityChart) {
        probabilityChart.destroy();
    }

    probabilityChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [prediction.fighter_a, prediction.fighter_b],
            datasets: [{
                data: [
                    (prediction.probability_a_wins * 100).toFixed(1),
                    (prediction.probability_b_wins * 100).toFixed(1)
                ],
                // Corner rojo = fighter_a, corner azul = fighter_b (consistente con las cards)
                backgroundColor: [CORNER_RED, CORNER_BLUE],
                borderColor: ARENA_BG,
                borderWidth: 3,
                hoverBorderWidth: 3,
                hoverBorderColor: ARENA_BG
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '62%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: CANVAS_MUTED,
                        padding: 20,
                        font: { family: 'Inter, system-ui, sans-serif' }
                    }
                },
                tooltip: {
                    backgroundColor: '#1D1D27',
                    titleColor: '#E7E5E4',
                    bodyColor: '#E7E5E4',
                    borderColor: '#2A2A36',
                    borderWidth: 1,
                    callbacks: {
                        label: (context) => ` ${context.label}: ${context.parsed}%`
                    }
                }
            }
        }
    });
}

// Iconos temáticos por factor + semántica del signo:
// los valores son diferencias A - B → positivo favorece al corner rojo (fighter_a),
// EXCEPTO la edad (invert: ser más joven es ventaja) y el factor de título (neutral → oro).
const FACTOR_META = [
    { match: 'reach', icon: 'fa-ruler-horizontal' },
    { match: 'height', icon: 'fa-ruler-vertical' },
    { match: 'age', icon: 'fa-cake-candles', invert: true },
    { match: 'win rate', icon: 'fa-chart-line' },
    { match: 'experience', icon: 'fa-clock-rotate-left' },
    { match: 'striking', icon: 'fa-hand-fist' },
    { match: 'takedown', icon: 'fa-user-ninja' },
    { match: 'title', icon: 'fa-trophy', neutral: true }
];

function getFactorMeta(factorName) {
    const name = factorName.toLowerCase();
    return FACTOR_META.find(meta => name.includes(meta.match)) || { icon: 'fa-scale-balanced' };
}

function displayKeyFactors(factors, prediction) {
    const container = document.getElementById('keyFactors');
    container.innerHTML = '';

    if (!factors || factors.length === 0) {
        container.innerHTML = '<p class="factor-empty">Sin factores significativos — pelea pareja en el papel.</p>';
        return;
    }

    factors.forEach(factor => {
        const meta = getFactorMeta(factor.factor);
        const favorRed = meta.invert ? factor.value < 0 : factor.value > 0;
        const cornerClass = meta.neutral ? 'factor-gold' : (favorRed ? 'factor-red' : 'factor-blue');
        const favorsText = meta.neutral ? 'Pelea titular' :
            `Favorece a ${favorRed ? prediction.fighter_a : prediction.fighter_b}`;
        const impactText = factor.impact === 'high' ? 'Impacto alto' : 'Impacto medio';

        const factorElement = document.createElement('div');
        factorElement.className = `factor-item ${cornerClass}`;

        // Construido con textContent (no innerHTML): los nombres de peleadores vienen del input del usuario
        const icon = document.createElement('i');
        icon.className = `fa-solid ${meta.icon} factor-icon`;

        const body = document.createElement('div');
        body.className = 'factor-body';
        const nameEl = document.createElement('span');
        nameEl.className = 'factor-name';
        nameEl.textContent = factor.factor;
        const favorsEl = document.createElement('span');
        favorsEl.className = 'factor-favors';
        favorsEl.textContent = favorsText;
        body.append(nameEl, favorsEl);

        const metrics = document.createElement('div');
        metrics.className = 'factor-metrics';
        const valueEl = document.createElement('span');
        valueEl.className = 'factor-value';
        valueEl.textContent = `${factor.value > 0 ? '+' : ''}${factor.value}`;
        const impactEl = document.createElement('span');
        impactEl.className = 'factor-impact';
        impactEl.textContent = impactText;
        metrics.append(valueEl, impactEl);

        factorElement.append(icon, body, metrics);
        container.appendChild(factorElement);
    });
}

function showLoading(show) {
    const modal = document.getElementById('loadingModal');
    if (show) {
        modal.classList.remove('hidden');
    } else {
        modal.classList.add('hidden');
    }
}
