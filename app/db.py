import os
import sqlite3
import psycopg2

# --- Configuration ---

# Get the database URL from the environment (for Render)
# Fallback to a local SQLite file for simple testing
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("DATABASE_URL not set, using local 'strength_log.db'")
    DATABASE_URL = 'sqlite:///strength_log.db'

# --- Database Functions ---

def _create_raw_connection():
    """Creates a raw, non-generator connection."""
    if DATABASE_URL.startswith('sqlite'):
        conn = sqlite3.connect(DATABASE_URL.replace('sqlite:///', ''), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
    else:
        conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_db_connection():
    """Create and yield a database connection (for FastAPI Depends)."""
    conn = _create_raw_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database using the schema.sql file."""
    print("Initializing database...")
    conn = _create_raw_connection()  # <-- FIX: Use raw connection
    try:
        with open('schema.sql', 'r') as f:
            schema_content = f.read()
            if isinstance(conn, sqlite3.Connection):
                conn.cursor().executescript(schema_content)
            else: # PostgreSQL
                cursor = conn.cursor()
                cursor.execute(schema_content)
                cursor.close()
        conn.commit()
        print("Database initialized.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
    finally:
        conn.close()  # <-- FIX: Close connection here

def init_db_if_needed():
    """Check if we need to init the DB (for local SQLite)"""
    if DATABASE_URL.startswith('sqlite'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        if not os.path.exists(db_path):
            init_db()

def workout_row_to_dict(row, cursor_desc=None):
    """Converts a database row (sqlite or psycopg2) into a dictionary."""
    if isinstance(row, sqlite3.Row):
        return dict(row)
    
    # For psycopg2 (row is a tuple)
    columns = [col[0] for col in cursor_desc]
    row_dict = dict(zip(columns, row))
    if 'weight_kg' in row_dict:
        row_dict['weight_kg'] = float(row_dict['weight_kg'])
    return row_dict

