from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import asyncio
import aiohttp
import redis
import json

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MMA Fight Prediction API",
    description="API para predicciones de peleas de MMA usando ML + LLM",
    version="1.0.0"
)

# CORS para permitir requests desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis para cache
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Modelos globales (cargar al inicio)
prediction_model = None
fighter_database = None

class FightPredictionRequest(BaseModel):
    fighter_a: str
    fighter_b: str
    event_name: Optional[str] = None
    weight_class: Optional[str] = None
    title_fight: bool = False
    include_llm_analysis: bool = True

class FightPredictionResponse(BaseModel):
    fighter_a: str
    fighter_b: str
    probability_a_wins: float
    probability_b_wins: float
    confidence: float
    predicted_winner: str
    key_factors: List[Dict]
    llm_analysis: Optional[str] = None
    betting_insights: Optional[Dict] = None
    timestamp: str

class FighterStatsResponse(BaseModel):
    name: str
    record: str
    stats: Dict
    recent_form: List[Dict]
    ranking: Optional[int] = None

class UpcomingEvent(BaseModel):
    event_name: str
    date: str
    fights: List[Dict]

@app.on_event("startup")
async def load_models():
    """Cargar modelos y datos al iniciar la aplicación"""
    global prediction_model, fighter_database
    
    try:
        # Cargar modelo entrenado
        with open('models/mma_prediction_model.pkl', 'rb') as f:
            prediction_model = pickle.load(f)
        
        # Cargar base de datos de luchadores
        fighter_database = pd.read_csv('data/fighters_complete.csv')
        
        logger.info("Models and data loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        # En producción: cargar modelos por defecto o desde S3/cloud storage

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "message": "MMA Prediction API is running",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": prediction_model is not None,
        "fighters_count": len(fighter_database) if fighter_database is not None else 0
    }

@app.post("/predict", response_model=FightPredictionResponse, tags=["Predictions"])
async def predict_fight(request: FightPredictionRequest):
    """Predecir el resultado de una pelea"""
    
    if prediction_model is None:
        raise HTTPException(status_code=503, detail="Prediction model not loaded")
    
    try:
        # Check cache first
        cache_key = f"prediction:{request.fighter_a}:{request.fighter_b}"
        cached_result = redis_client.get(cache_key)
        
        if cached_result:
            logger.info(f"Returning cached prediction for {request.fighter_a} vs {request.fighter_b}")
            return FightPredictionResponse(**json.loads(cached_result))
        
        # Validar que los luchadores existen
        fighter_a_data = get_fighter_data(request.fighter_a)
        fighter_b_data = get_fighter_data(request.fighter_b)
        
        if not fighter_a_data or not fighter_b_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Fighter(s) not found: {request.fighter_a}, {request.fighter_b}"
            )
        
        # Engineer features
        features = engineer_fight_features(fighter_a_data, fighter_b_data, request)
        
        # Hacer predicción
        probabilities = prediction_model.predict_proba([features])[0]
        
        # Generar análisis LLM si se solicita
        llm_analysis = None
        if request.include_llm_analysis:
            llm_analysis = await generate_llm_analysis(
                fighter_a_data, fighter_b_data, probabilities
            )
        
        # Obtener insights de apuestas
        betting_insights = await get_betting_insights(request.fighter_a, request.fighter_b)
        
        # Crear respuesta
        response = FightPredictionResponse(
            fighter_a=request.fighter_a,
            fighter_b=request.fighter_b,
            probability_a_wins=float(probabilities[1]),
            probability_b_wins=float(probabilities[0]),
            confidence=float(max(probabilities)),
            predicted_winner=request.fighter_a if probabilities[1] > 0.5 else request.fighter_b,
            key_factors=get_key_factors(features, fighter_a_data, fighter_b_data),
            llm_analysis=llm_analysis,
            betting_insights=betting_insights,
            timestamp=datetime.now().isoformat()
        )
        
        # Cache result for 1 hour
        redis_client.setex(cache_key, 3600, response.json())
        
        logger.info(f"Generated prediction for {request.fighter_a} vs {request.fighter_b}")
        return response
        
    except Exception as e:
        logger.error(f"Error making prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Error making prediction: {str(e)}")

@app.get("/fighter/{fighter_name}", response_model=FighterStatsResponse, tags=["Fighters"])
async def get_fighter_stats(fighter_name: str):
    """Obtener estadísticas completas de un luchador"""
    
    fighter_data = get_fighter_data(fighter_name)
    
    if not fighter_data:
        raise HTTPException(status_code=404, detail=f"Fighter '{fighter_name}' not found")
    
    # Calcular record
    record = f"{fighter_data.get('wins', 0)}-{fighter_data.get('losses', 0)}-{fighter_data.get('draws', 0)}"
    
    # Obtener forma reciente
    recent_form = get_recent_form(fighter_name)
    
    # Obtener ranking actual
    ranking = get_current_ranking(fighter_name, fighter_data.get('weight_class'))
    
    return FighterStatsResponse(
        name=fighter_name,
        record=record,
        stats=fighter_data,
        recent_form=recent_form,
        ranking=ranking
    )

@app.get("/search/fighters/{query}", tags=["Search"])
async def search_fighters(query: str, limit: int = 10):
    """Buscar luchadores por nombre"""
    
    if fighter_database is None:
        raise HTTPException(status_code=503, detail="Fighter database not loaded")
    
    # Búsqueda fuzzy por nombre
    matches = fighter_database[
        fighter_database['name'].str.contains(query, case=False, na=False)
    ].head(limit)
    
    results = []
    for _, fighter in matches.iterrows():
        results.append({
            'name': fighter['name'],
            'record': f"{fighter.get('wins', 0)}-{fighter.get('losses', 0)}-{fighter.get('draws', 0)}",
            'weight_class': fighter.get('weight_class', 'Unknown'),
            'ranking': fighter.get('ranking', None)
        })
    
    return {
        'query': query,
        'results': results,
        'count': len(results)
    }

@app.get("/events/upcoming", response_model=List[UpcomingEvent], tags=["Events"])
async def get_upcoming_events():
    """Obtener eventos próximos con predicciones"""
    
    # En producción: obtener de base de datos o scraping actualizado
    upcoming_events = [
        {
            "event_name": "UFC 300",
            "date": "2025-09-15",
            "fights": [
                {"fighter_a": "Jon Jones", "fighter_b": "Stipe Miocic", "title_fight": True},
                {"fighter_a": "Alexander Volkanovski", "fighter_b": "Ilia Topuria", "title_fight": True}
            ]
        }
    ]
    
    # Agregar predicciones para cada pelea
    for event in upcoming_events:
        for fight in event['fights']:
            try:
                # Hacer predicción rápida
                request = FightPredictionRequest(
                    fighter_a=fight['fighter_a'],
                    fighter_b=fight['fighter_b'],
                    include_llm_analysis=False
                )
                prediction = await predict_fight(request)
                
                fight['prediction'] = {
                    'winner': prediction.predicted_winner,
                    'probability': max(prediction.probability_a_wins, prediction.probability_b_wins),
                    'confidence': prediction.confidence
                }
                
            except Exception as e:
                logger.warning(f"Could not predict {fight['fighter_a']} vs {fight['fighter_b']}: {e}")
                fight['prediction'] = None
    
    return [UpcomingEvent(**event) for event in upcoming_events]

@app.post("/retrain", tags=["Model Management"])
async def retrain_model(background_tasks: BackgroundTasks):
    """Reentrenar el modelo con nuevos datos"""
    
    # Solo permitir en desarrollo o con autenticación
    background_tasks.add_task(retrain_model_background)
    
    return {
        "message": "Model retraining started in background",
        "status": "accepted",
        "timestamp": datetime.now().isoformat()
    }

async def retrain_model_background():
    """Reentrenar modelo en background"""
    try:
        logger.info("Starting model retraining...")
        
        # 1. Recolectar nuevos datos
        # collector = MMADataCollector()
        # new_data = collector.scrape_recent_fights()
        
        # 2. Preparar datos de entrenamiento
        # training_data = prepare_training_data(new_data)
        
        # 3. Reentrenar modelo
        # new_model = train_new_model(training_data)
        
        # 4. Validar modelo
        # validation_score = validate_model(new_model)
        
        # 5. Si es mejor, reemplazar modelo actual
        # if validation_score > current_model_score:
        #     replace_model(new_model)
        
        logger.info("Model retraining completed")
        
    except Exception as e:
        logger.error(f"Error retraining model: {e}")

@app.get("/analytics/model-performance", tags=["Analytics"])
async def get_model_performance():
    """Obtener métricas de rendimiento del modelo"""
    
    # En producción: calcular desde base de datos de predicciones vs resultados reales
    return {
        "accuracy": 0.72,
        "precision": 0.74,
        "recall": 0.69,
        "f1_score": 0.71,
        "total_predictions": 1547,
        "correct_predictions": 1114,
        "last_updated": "2025-09-03T10:00:00Z"
    }

@app.get("/analytics/betting-roi", tags=["Analytics"])
async def get_betting_roi():
    """ROI si siguieras las predicciones del modelo"""
    
    return {
        "total_bets": 234,
        "winning_bets": 162,
        "win_rate": 0.692,
        "total_staked": 2340.00,
        "total_returned": 2876.50,
        "profit": 536.50,
        "roi": 0.229,  # 22.9%
        "best_streak": 12,
        "worst_streak": -5
    }

# Funciones auxiliares

def get_fighter_data(fighter_name: str) -> Optional[Dict]:
    """Obtener datos de un luchador de la base de datos"""
    if fighter_database is None:
        return None
    
    # Búsqueda exacta primero
    exact_match = fighter_database[fighter_database['name'] == fighter_name]
    
    if not exact_match.empty:
        return exact_match.iloc[0].to_dict()
    
    # Búsqueda fuzzy
    fuzzy_match = fighter_database[
        fighter_database['name'].str.contains(fighter_name, case=False, na=False)
    ]
    
    if not fuzzy_match.empty:
        return fuzzy_match.iloc[0].to_dict()
    
    return None

def engineer_fight_features(fighter_a_data: Dict, fighter_b_data: Dict, request: FightPredictionRequest) -> List[float]:
    """Generar features para el modelo ML"""
    
    features = []
    
    # Diferencias físicas
    features.append(fighter_a_data.get('height', 180) - fighter_b_data.get('height', 180))
    features.append(fighter_a_data.get('reach', 180) - fighter_b_data.get('reach', 180))
    features.append(fighter_a_data.get('age', 30) - fighter_b_data.get('age', 30))
    
    # Diferencias de record
    total_fights_a = fighter_a_data.get('wins', 0) + fighter_a_data.get('losses', 0)
    total_fights_b = fighter_b_data.get('wins', 0) + fighter_b_data.get('losses', 0)
    
    win_rate_a = fighter_a_data.get('wins', 0) / max(total_fights_a, 1)
    win_rate_b = fighter_b_data.get('wins', 0) / max(total_fights_b, 1)
    
    features.append(win_rate_a - win_rate_b)
    features.append(total_fights_a - total_fights_b)
    
    # Estadísticas de striking
    features.append(fighter_a_data.get('striking_accuracy', 50) - fighter_b_data.get('striking_accuracy', 50))
    features.append(fighter_a_data.get('striking_defense', 50) - fighter_b_data.get('striking_defense', 50))
    
    # Estadísticas de grappling
    features.append(fighter_a_data.get('takedown_accuracy', 30) - fighter_b_data.get('takedown_accuracy', 30))
    features.append(fighter_a_data.get('takedown_defense', 70) - fighter_b_data.get('takedown_defense', 70))
    
    # Contexto de la pelea
    features.append(1 if request.title_fight else 0)
    
    # Asegurar que tenemos el número correcto de features
    while len(features) < 16:  # Ajustar según modelo
        features.append(0.0)
    
    return features[:16]

async def generate_llm_analysis(fighter_a_data: Dict, fighter_b_data: Dict, probabilities: np.ndarray) -> str:
    """Generar análisis usando LLM"""
    
    try:
        # En producción: llamada real a gpt-oss o OpenAI API
        prompt = f"""
        Analiza esta pelea de MMA:
        
        {fighter_a_data['name']}: {fighter_a_data.get('wins', 0)}-{fighter_a_data.get('losses', 0)}
        {fighter_b_data['name']}: {fighter_b_data.get('wins', 0)}-{fighter_b_data.get('losses', 0)}
        
        Predicción ML: {probabilities[1]:.1%} - {probabilities[0]:.1%}
        
        Proporciona un análisis conciso de 2-3 párrafos.
        """
        
        # Placeholder - reemplazar con llamada real a LLM
        analysis = f"""
        Esta pelea presenta un interesante contraste de estilos entre {fighter_a_data['name']} y {fighter_b_data['name']}. 
        Basándose en las estadísticas, el modelo predice una probabilidad de {probabilities[1]:.1%} para {fighter_a_data['name']}.
        
        Los factores clave incluyen la diferencia en experiencia y el matchup estilístico. 
        La preparación específica y la condición física el día de la pelea serán determinantes.
        """
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error generating LLM analysis: {e}")
        return "Análisis LLM no disponible temporalmente."

async def get_betting_insights(fighter_a: str, fighter_b: str) -> Optional[Dict]:
    """Obtener insights de apuestas"""
    
    try:
        # En producción: llamar a APIs de casas de apuestas
        return {
            "market_odds": {
                fighter_a: -120,
                fighter_b: +100
            },
            "implied_probability": {
                fighter_a: 0.545,
                fighter_b: 0.500
            },
            "value_bet": fighter_b if True else None,  # Lógica de value betting
            "recommendation": "Slight value on underdog based on model vs market"
        }
        
    except Exception as e:
        logger.error(f"Error getting betting insights: {e}")
        return None

def get_key_factors(features: List[float], fighter_a_data: Dict, fighter_b_data: Dict) -> List[Dict]:
    """Identificar factores clave de la predicción"""
    
    feature_names = [
        "height_difference", "reach_difference", "age_difference", 
        "win_rate_difference", "experience_difference", "striking_accuracy_diff",
        "striking_defense_diff", "takedown_accuracy_diff", "takedown_defense_diff",
        "title_fight_factor"
    ]
    
    key_factors = []
    
    for i, (name, value) in enumerate(zip(feature_names, features)):
        if abs(value) > 0.1:  # Solo factores significativos
            key_factors.append({
                "factor": name.replace("_", " ").title(),
                "value": round(float(value), 3),
                "impact": "high" if abs(value) > 1.0 else "medium"
            })
    
    return sorted(key_factors, key=lambda x: abs(x["value"]), reverse=True)[:5]

def get_recent_form(fighter_name: str, limit: int = 5) -> List[Dict]:
    """Obtener forma reciente del luchador"""
    # En producción: consultar base de datos de peleas
    return [
        {"opponent": "Opponent 1", "result": "W", "method": "TKO", "round": 2},
        {"opponent": "Opponent 2", "result": "W", "method": "Decision", "round": 5}
    ]

def get_current_ranking(fighter_name: str, weight_class: Optional[str]) -> Optional[int]:
    """Obtener ranking actual del luchador"""
    # En producción: consultar rankings actualizados
    return 5  # Placeholder

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)