-- Schema para MMA Fight Predictor

-- Tabla de luchadores
CREATE TABLE IF NOT EXISTS fighters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    height FLOAT,
    reach FLOAT,
    age INTEGER,
    weight_class VARCHAR(50),
    ranking INTEGER,
    striking_accuracy FLOAT,
    striking_defense FLOAT,
    takedown_accuracy FLOAT,
    takedown_defense FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de peleas
CREATE TABLE IF NOT EXISTS fights (
    id SERIAL PRIMARY KEY,
    fighter_a_name VARCHAR(255),
    fighter_b_name VARCHAR(255),
    event_name VARCHAR(255),
    fight_date DATE,
    winner VARCHAR(255),
    method VARCHAR(50),
    round INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de predicciones
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    fighter_a VARCHAR(255),
    fighter_b VARCHAR(255),
    probability_a FLOAT,
    probability_b FLOAT,
    predicted_winner VARCHAR(255),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datos de prueba
INSERT INTO fighters (name, wins, losses, draws, height, reach, age, weight_class, ranking) VALUES
('Jon Jones', 27, 1, 0, 193, 215, 36, 'heavyweight', 1),
('Stipe Miocic', 20, 4, 0, 193, 203, 41, 'heavyweight', 2),
('Alexander Volkanovski', 26, 3, 0, 168, 183, 35, 'featherweight', 1),
('Ilia Topuria', 15, 0, 0, 170, 178, 27, 'featherweight', 2)
ON CONFLICT (name) DO NOTHING;
