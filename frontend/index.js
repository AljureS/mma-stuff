// Configuration
const API_BASE_URL = 'http://localhost:8000';

// State
let currentPrediction = null;
let probabilityChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    initializeEventListeners();
    loadUpcomingEvents();
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

        displayPredictionResults(prediction);

    } catch (error) {
        console.error('Error making prediction:', error);
        alert(`Error: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

function displayPredictionResults(prediction) {
    // Show results section
    document.getElementById('resultsSection').classList.remove('hidden');

    // Update summary
    document.getElementById('predictedWinner').textContent = prediction.predicted_winner;
    document.getElementById('confidence').textContent = `${(prediction.confidence * 100).toFixed(1)}%`;

    const winnerProb = prediction.predicted_winner === prediction.fighter_a ?
        prediction.probability_a_wins : prediction.probability_b_wins;
    document.getElementById('winProbability').textContent = `${(winnerProb * 100).toFixed(1)}%`;

    // Update chart
    updateProbabilityChart(prediction);

    // Update key factors
    displayKeyFactors(prediction.key_factors);

    // Update AI analysis
    document.getElementById('llmAnalysis').textContent =
        prediction.llm_analysis || 'Análisis no disponible';

    // Update betting insights
    if (prediction.betting_insights) {
        displayBettingInsights(prediction.betting_insights);
    }

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
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
                backgroundColor: ['#3B82F6', '#EF4444'],
                borderWidth: 0,
                hoverBorderWidth: 2,
                hoverBorderColor: '#FFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#FFF',
                        padding: 20
                    }
                }
            }
        }
    });
}

function displayKeyFactors(factors) {
    const container = document.getElementById('keyFactors');
    container.innerHTML = '';

    factors.forEach(factor => {
        const factorElement = document.createElement('div');
        factorElement.className = 'flex justify-between items-center bg-gray-600 p-3 rounded';

        const impactColor = factor.impact === 'high' ? 'text-red-400' : 'text-yellow-400';

        factorElement.innerHTML = `
                    <span class="text-gray-300">${factor.factor}</span>
                    <div class="flex items-center">
                        <span class="text-white font-semibold mr-2">${factor.value}</span>
                        <span class="${impactColor} text-sm">${factor.impact.toUpperCase()}</span>
                    </div>
                `;

        container.appendChild(factorElement);
    });
}

function displayBettingInsights(insights) {
    const marketOddsDiv = document.getElementById('marketOdds');
    const recommendationDiv = document.getElementById('bettingRecommendation');

    // Market odds
    if (insights.market_odds) {
        let oddsHtml = '';
        Object.entries(insights.market_odds).forEach(([fighter, odds]) => {
            const sign = odds > 0 ? '+' : '';
            oddsHtml += `<div class="flex justify-between"><span>${fighter}:</span><span>${sign}${odds}</span></div>`;
        });
        marketOddsDiv.innerHTML = oddsHtml;
    }

    // Recommendation
    if (insights.recommendation) {
        recommendationDiv.textContent = insights.recommendation;
    }
}

async function loadUpcomingEvents() {
    try {
        const response = await fetch(`${API_BASE_URL}/events/upcoming`);
        const events = await response.json();

        const container = document.getElementById('upcomingEvents');
        container.innerHTML = '';

        events.forEach(event => {
            const eventElement = document.createElement('div');
            eventElement.className = 'bg-gray-700 rounded-lg p-6 mb-4';

            let fightsHtml = '';
            event.fights.forEach(fight => {
                const predictionInfo = fight.prediction ?
                    `<span class="text-green-400 text-sm">${fight.prediction.winner} (${(fight.prediction.probability * 100).toFixed(0)}%)</span>` :
                    '<span class="text-gray-400 text-sm">Sin predicción</span>';

                fightsHtml += `
                            <div class="flex justify-between items-center bg-gray-600 p-3 rounded mb-2">
                                <div>
                                    <span class="font-semibold">${fight.fighter_a}</span>
                                    <span class="text-gray-400 mx-2">vs</span>
                                    <span class="font-semibold">${fight.fighter_b}</span>
                                    ${fight.title_fight ? '<span class="bg-yellow-500 text-black px-2 py-1 rounded text-xs ml-2">TÍTULO</span>' : ''}
                                </div>
                                <div>${predictionInfo}</div>
                            </div>
                        `;
            });

            eventElement.innerHTML = `
                        <h3 class="text-xl font-semibold mb-2">${event.event_name}</h3>
                        <p class="text-gray-400 mb-4">${new Date(event.date).toLocaleDateString('es-ES', {
                weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
            })}</p>
                        <div>${fightsHtml}</div>
                    `;

            container.appendChild(eventElement);
        });

    } catch (error) {
        console.error('Error loading upcoming events:', error);
        document.getElementById('upcomingEvents').innerHTML =
            '<p class="text-gray-400">Error cargando eventos próximos</p>';
    }
}

function showLoading(show) {
    const modal = document.getElementById('loadingModal');
    if (show) {
        modal.classList.remove('hidden');
    } else {
        modal.classList.add('hidden');
    }
}
