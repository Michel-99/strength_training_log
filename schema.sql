-- Create the main workout table
-- Use "CREATE TABLE IF NOT EXISTS" to avoid errors on restart
CREATE TABLE IF NOT EXISTS workout (
  id SERIAL PRIMARY KEY,
  exercise_name TEXT NOT NULL,
  weight_kg NUMERIC NOT NULL,
  set INTEGER NOT NULL,
  reps INTEGER NOT NULL,
  log_date BIGINT NOT NULL
);