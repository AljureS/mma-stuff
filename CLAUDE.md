# MMA Fight Predictor - Guía Completa del Proyecto

> **⚠️ IMPORTANTE - DOCUMENTACIÓN SINCRONIZADA**
> 
> Este archivo `CLAUDE.md` contiene la documentación completa y actualizada del proyecto MMA Fight Predictor.
> 
> **CUALQUIER CAMBIO realizado a CUALQUIER archivo del proyecto (código, configuración, estructura, etc.) DEBE reflejarse inmediatamente en este archivo de documentación.**
> 
> Esto incluye:
> - Modificaciones en archivos Python (.py)
> - Cambios en el frontend HTML/CSS/JS
> - Actualizaciones en configuración o deployment
> - Nuevas funcionalidades o endpoints
> - Cambios en la estructura de datos
> - Modificaciones en dependencias o tecnologías
> 
> **La documentación debe mantenerse como la fuente única de verdad del proyecto.**

## ¿Qué es este proyecto?

Este es un **sistema de predicción de peleas de MMA** que utiliza **Inteligencia Artificial** para predecir quién ganará en un combate de artes marciales mixtas. El sistema combina datos históricos de peleadores, estadísticas de combate y análisis inteligente para generar predicciones precisas.

## ¿Cómo funciona en términos simples?

Imagínate que tienes un experto en MMA que ha visto miles de peleas y puede recordar las estadísticas de cada peleador. Este sistema hace exactamente eso, pero de forma automatizada:

1. **Recopila información** de peleadores (altura, peso, récord, estilo de pelea)
2. **Analiza patrones** de victorias y derrotas 
3. **Compara** las estadísticas de dos peleadores
4. **Calcula probabilidades** de victoria para cada uno
5. **Genera un análisis** explicando por qué un peleador tiene ventaja

## Arquitectura del Sistema

El proyecto está dividido en **4 componentes principales**:

### 1. **Recolección de Datos** (`scripts/data_collection.py`)
**¿Qué hace?** Obtiene información actualizada de peleadores desde internet.

**Fuentes de datos:**
- **UFCStats.com**: Estadísticas oficiales de la UFC
- **Sherdog**: Rankings y datos históricos
- **Tapology**: Eventos futuros
- **APIs de casas de apuestas**: Probabilidades del mercado (solo para comparación post-predicción)
- **Redes sociales**: Sentimiento público

**Datos que recopila:**
- Información básica: nombre, altura, peso, alcance, edad
- Récord de peleas: victorias, derrotas, empates
- Estadísticas técnicas: precisión de golpes, defensa, derribos
- Historial de peleas: métodos de victoria, oponentes
- Rankings actuales por división

**⚠️ IMPORTANTE sobre Odds de Apuestas:**
Las odds de casas de apuestas **NO afectan la predicción del modelo**. Se recopilan únicamente para:
- Comparar la predicción del modelo con el mercado (post-predicción)
- Identificar oportunidades de "value betting"
- Validar la precisión del modelo contra el consenso del mercado
- Las odds NO son una de las 16 variables del modelo ML

### 2. **Motor de Predicción** (`api/ml_system.py`)
**¿Qué hace?** El "cerebro" que procesa los datos y hace las predicciones.

**Cómo funciona:**
1. **Carga datos** de ambos peleadores
2. **Calcula las 16 features** (variables de entrada del modelo)
3. **Genera puntuaciones compuestas** usando algoritmos específicos
4. **Usa Machine Learning** (XGBoost) para predecir el resultado
5. **Genera análisis** usando IA para explicar la predicción

**Las 16 Variables (Features) del Modelo ML:**

**Diferencias Físicas:**
1. `height_diff` - Diferencia de altura (cm)
2. `reach_diff` - Diferencia de alcance (cm)
3. `age_diff` - Diferencia de edad (años)

**Diferencias de Experiencia y Efectividad:**
4. `experience_diff` - Diferencia en peleas totales
5. `win_rate_diff` - Diferencia en tasa de victorias (%)
6. `finish_rate_diff` - Diferencia en tasa de finalizaciones (KO/Sub vs Decisión)

**Diferencias en Striking (Golpeo):**
7. `sig_str_acc_diff` - Diferencia en precisión de golpes significativos (%)
8. `sig_str_def_diff` - Diferencia en defensa de golpes (%)

**Diferencias en Grappling (Lucha):**
9. `takedown_acc_diff` - Diferencia en precisión de derribos (%)
10. `takedown_def_diff` - Diferencia en defensa de derribos (%)

**Scores Compuestos (calculados por el sistema):**
11. `power_score_diff` - Diferencia en poder de knockout (basado en knockdowns y KO rate)
12. `grappling_score_diff` - Diferencia en habilidad de suelo (takedowns + sumisiones)
13. `cardio_score_diff` - Diferencia en resistencia (duración promedio de peleas)

**Análisis Avanzado:**
14. `recent_form_diff` - Diferencia en forma reciente (últimas 3-5 peleas)
15. `opponent_quality_diff` - Diferencia en calidad de oponentes enfrentados
16. `style_matchup_score` - Análisis de compatibilidad de estilos (striker vs grappler)

**Características especiales:**
- Análisis de estilos (striker vs grappler)
- Consideración de forma reciente (racha de victorias/derrotas)
- Factores contextuales (pelea por título, categoría de peso)

### 3. **API Backend** (`api/main.py`)
**¿Qué hace?** Servidor que conecta el frontend con el motor de predicción.

**Endpoints principales:**
- `POST /predict`: Realiza una predicción de pelea
- `GET /fighter/{name}`: Obtiene estadísticas de un peleador
- `GET /search/fighters/{query}`: Busca peleadores por nombre
- `GET /events/upcoming`: Lista eventos próximos con predicciones
- `GET /analytics/model-performance`: Métricas del modelo
- `GET /analytics/betting-roi`: ROI hipotético siguiendo las predicciones
- `POST /retrain`: Reentrenar el modelo con datos nuevos

**Características técnicas:**
- **FastAPI**: Framework web rápido y moderno
- **Cache con Redis**: Almacena predicciones por 1 hora (key: `prediction:{fighter_a}:{fighter_b}`)
- **CORS habilitado**: Permite requests desde el frontend
- **Validación de datos**: Usando Pydantic
- **Manejo de errores**: Respuestas detalladas de errores
- **Background tasks**: Reentrenamiento de modelo en segundo plano

**Flujo de Predicción:**
1. Validar que peleadores existen en base de datos
2. Verificar cache de Redis (si existe, retornar inmediatamente)
3. Cargar datos completos de ambos peleadores
4. Calcular las 16 features del modelo
5. Ejecutar predicción con XGBoost
6. Generar análisis LLM (opcional)
7. **DESPUÉS de la predicción**: Obtener odds de apuestas para comparación
8. Retornar resultado y guardarlo en cache por 1 hora

### 4. **Frontend Web** (`mma_frontend.html`)
**¿Qué hace?** Interfaz visual para que los usuarios hagan predicciones.

**Funcionalidades:**
- **Formulario de predicción**: Seleccionar dos peleadores
- **Búsqueda automática**: Encuentra peleadores mientras escribes
- **Visualización de resultados**: Gráficos y estadísticas
- **Análisis IA**: Explicación detallada de la predicción
- **Insights de apuestas**: Comparación con odds del mercado
- **Eventos próximos**: Lista de peleas futuras

**Tecnologías usadas:**
- **HTML5 + CSS3**: Estructura y estilos
- **TailwindCSS**: Framework de estilos moderno
- **JavaScript**: Lógica de interacción
- **Chart.js**: Gráficos de probabilidades
- **Font Awesome**: Iconos

## Flujo de Trabajo Completo

### Paso 1: Usuario hace una predicción
1. Usuario abre el frontend en el navegador
2. Escribe nombres de dos peleadores
3. Sistema busca automáticamente y muestra sus estadísticas
4. Usuario selecciona opciones (categoría, evento, título)
5. Hace clic en "Predecir Resultado"

### Paso 2: Procesamiento backend
1. Frontend envía petición POST a `/predict`
2. API verifica cache de Redis (si existe, retorna inmediatamente)
3. API valida que los peleadores existen en base de datos
4. Sistema carga datos completos de ambos peleadores
5. Motor de predicción calcula las **16 features** del modelo
6. Modelo XGBoost genera probabilidades de victoria
7. IA genera análisis cualitativo (opcional)
8. **DESPUÉS de la predicción**: Sistema obtiene odds de apuestas para comparación
9. Resultado se guarda en cache Redis por 1 hora

### Paso 3: Presentación de resultados
1. API envía respuesta con predicción completa
2. Frontend muestra:
   - Ganador predicho y probabilidad
   - Gráfico circular de probabilidades
   - Factores clave que influyen (las features más significativas)
   - Análisis detallado de IA
   - **Comparación post-predicción** con odds de apuestas (no usadas en el cálculo)

## Tecnologías Utilizadas

### Backend (Python)
- **FastAPI**: Framework web asíncrono
- **Pandas**: Manipulación de datos
- **XGBoost**: Algoritmo de Machine Learning
- **Scikit-learn**: Herramientas de ML
- **Redis**: Cache en memoria
- **Requests + BeautifulSoup**: Web scraping
- **Pydantic**: Validación de datos

### Frontend
- **HTML5/CSS3**: Estructura base
- **TailwindCSS**: Estilos responsive
- **JavaScript ES6**: Lógica del cliente
- **Chart.js**: Visualizaciones
- **Font Awesome**: Iconografía

### Infraestructura
- **PostgreSQL**: Base de datos principal
- **Redis**: Cache y sesiones
- **Nginx**: Servidor web reverso
- **Docker**: Contenedorización
- **Supervisor**: Gestión de procesos

## Archivos del Proyecto

### Archivos Principales
- `api/main.py`: Servidor FastAPI con todos los endpoints
- `api/ml_system.py`: Motor de predicción con ML y las 16 features
- `scripts/data_collection.py`: Sistema de recolección de datos (web scraping)
- `frontend/mma_frontend.html`: Interfaz web completa
- `CLAUDE.md`: Documentación completa del proyecto (este archivo)

### Estructura de Datos
```
data/
├── fighters_complete.csv      # Base de datos de peleadores
├── fight_history.csv          # Historial de peleas
└── training_data.csv          # Datos para entrenar el modelo

models/
└── mma_prediction_model.pkl   # Modelo ML entrenado
```

## Cómo Ejecutar el Proyecto

### Opción 1: Desarrollo Local
```bash
# 1. Instalar dependencias
pip install fastapi uvicorn pandas numpy xgboost scikit-learn redis

# 2. Iniciar Redis
redis-server

# 3. Ejecutar API
python mma_prediction_api.py

# 4. Abrir frontend
# Servir mma_frontend.html en un servidor web local
```

### Opción 2: Instalación Completa
```bash
# Ejecutar script de instalación (Linux)
chmod +x deployment_setup.sh
./deployment_setup.sh
```

## Características Técnicas Avanzadas

### Machine Learning
- **Algoritmo**: XGBoost (Gradient Boosting)
- **Tipo**: Clasificación binaria (Ganador A o B)
- **Features**: 16 variables exactas (listadas en sección "Motor de Predicción")
- **Validación**: Train/test split 80/20 con early stopping (50 rounds)
- **Métricas**: Accuracy, Log Loss, F1-Score
- **Hiperparámetros**:
  - `n_estimators=1000`
  - `learning_rate=0.01`
  - `max_depth=6`
  - `subsample=0.8`
  - `colsample_bytree=0.8`
- **Feature Importance**: El modelo calcula automáticamente qué variables tienen más impacto en las predicciones

### Sistema de Cache con Redis
- **Redis**: Base de datos en memoria (RAM) para cache ultra-rápido
- **Tiempo de expiración**: 1 hora (3600 segundos)
- **Key format**: `prediction:{fighter_a}:{fighter_b}`
- **Ventajas**:
  - Primera petición: ~3 segundos (procesamiento completo)
  - Peticiones subsecuentes: ~5 milisegundos (desde cache)
  - Maneja miles de requests simultáneos sin colapsar
  - Crucial para eventos UFC populares con alta demanda
- **Expiración automática**: Después de 1 hora, los datos se borran automáticamente para mantener frescura

### Web Scraping Inteligente
- **Rate limiting**: Pausas de 1-2 segundos entre requests para evitar bans
- **Headers personalizados**: User-Agent simulando navegador real
- **Manejo de errores**: Continúa aunque falle una página/fuente
- **Parsing robusto**: BeautifulSoup para manejar cambios en HTML
- **Fuentes múltiples**: Si una falla, las otras compensan

### Análisis de IA con LLM
- **Integración LLM**: Preparado para GPT/Claude/modelos locales
- **Prompts estructurados**: Análisis consistente y objetivo
- **Contexto rico**: Incluye estadísticas, récords, estilos de pelea
- **Opcional**: Puede desactivarse para respuestas más rápidas
- **Fallback**: Análisis básico si LLM falla o no está disponible

### Betting Insights (Post-Predicción)
- **Timing**: Se obtienen DESPUÉS de generar la predicción del modelo
- **Propósito**: Comparar predicción del modelo vs consenso del mercado
- **Value Betting**: Identificar oportunidades donde el modelo discrepa del mercado
- **NO afectan predicción**: Las odds NO son input del modelo ML
- **Fuentes**: APIs de casas de apuestas (DraftKings, Bet365, etc.)

## Posibles Mejoras Futuras

### Datos
- Integrar más fuentes (ESPN, MMA Junkie)
- Análisis de video (tendencias técnicas)
- Datos biomédicos (lesiones, cortes de peso)
- Factores psicológicos (traumas de derrotas)

### Modelo
- Deep Learning (redes neuronales)
- Ensemble methods (múltiples modelos)
- Análisis temporal (evolución del peleador)
- Features más sofisticadas

### Funcionalidades
- Predicciones de rounds específicos
- Método de victoria (KO, sumisión, decisión)
- Análisis de riesgo/recompensa para apuestas
- Simulación de torneos completos

## Consideraciones Importantes

### Limitaciones
- **Datos históricos**: Solo tan bueno como los datos disponibles
- **Factores impredecibles**: Lesiones de último minuto, factores mentales
- **Contexto específico**: Cada pelea es única
- **Sesgos**: Puede favorecer estilos o peleadores populares

### Uso Responsable
- **Entretenimiento**: Principalmente para análisis y diversión
- **Apuestas**: Usar con moderación y responsabilidad
- **No garantías**: Las predicciones no son certezas
- **Complemento**: Combinar con análisis humano experto

## Conclusión

Este proyecto demuestra cómo la tecnología moderna puede aplicarse al deporte, combinando:
- **Ciencia de datos** para procesar información masiva
- **Machine Learning** para encontrar patrones complejos  
- **Desarrollo web** para crear interfaces intuitivas
- **Análisis de IA** para generar insights valiosos

Es un ejemplo completo de un **sistema de predicción deportiva end-to-end**, desde la recolección de datos hasta la presentación de resultados, que puede adaptarse a otros deportes o casos de uso similares.
- Siempre que cambien los archivos, actualiza el archivo CLAUDE.md