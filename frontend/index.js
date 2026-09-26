// Configuration
const API_BASE_URL = 'http://localhost:8000';

// State
let currentPrediction = null;
let probabilityChart = null;

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

    // Fighter inputs with debounced search
    let debounceTimer;
    ['fighterA', 'fighterB'].forEach(id => {
        document.getElementById(id).addEventListener('input', function (e) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => searchFighter(id, e.target.value), 500);
        });
    });
}

async function searchFighter(inputId, query) {
    if (query.length < 2) return;

    try {
        const response = await fetch(`${API_BASE_URL}/search/fighters/${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.results && data.results.length > 0) {
            const fighter = data.results[0];
            updateFighterStats(inputId, fighter);
        }
    } catch (error) {
        console.error('Error searching fighter:', error);
    }
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

async function makePrediction() {
    const fighterA = document.getElementById('fighterA').value.trim();
    const fighterB = document.getElementById('fighterB').value.trim();

    if (!fighterA || !fighterB) {
        alert('Por favor ingresa ambos luchadores');
        return;
    }

    if (fighterA.toLowerCase() === fighterB.toLowerCase()) {
        alert('Los luchadores deben ser diferentes');
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
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Error making prediction');
        }

        const prediction = await response.json();
        currentPrediction = prediction;

        displayPredictionResults(prediction, requestData.title_fight);

    } catch (error) {
        console.error('Error making prediction:', error);
        alert(`Error: ${error.message}`);
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

        factorElement.innerHTML = `
            <i class="fa-solid ${meta.icon} factor-icon"></i>
            <div class="factor-body">
                <span class="factor-name">${factor.factor}</span>
                <span class="factor-favors">${favorsText}</span>
            </div>
            <div class="factor-metrics">
                <span class="factor-value">${factor.value > 0 ? '+' : ''}${factor.value}</span>
                <span class="factor-impact">${impactText}</span>
            </div>
        `;

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
