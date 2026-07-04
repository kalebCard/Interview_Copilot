import sqlite3
from pathlib import Path
import time
import logging
from typing import List, Tuple
from copilot.core.config import PROJECT_ROOT

try:
    import tiktoken
except ImportError:
    tiktoken = None

DB_PATH = PROJECT_ROOT / "data" / "interviews.db"

_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return
    _db_initialized = True
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp REAL,
                category TEXT,
                question TEXT,
                answer TEXT,
                feedback TEXT
            )
        """)



def add_interaction(session_id: str, question: str, answer: str, category: str = "general"):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO interactions (session_id, timestamp, category, question, answer) VALUES (?, ?, ?, ?, ?)",
                (session_id, time.time(), category, question, answer)
            )
            conn.commit()
    except sqlite3.OperationalError as e:
        logging.error(f"Error guardando interacción: {e}")

def get_recent_context(session_id: str, max_tokens: int = 2000) -> List[str]:
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT question, answer FROM interactions WHERE session_id = ? ORDER BY timestamp ASC LIMIT 100",
                (session_id,)
            )
            rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logging.error(f"Error al leer contexto: {e}")
        return []
        
    context: List[str] = []
    current_tokens: float = 0.0
    
    if tiktoken is not None:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        def estimate_tokens(text): return len(encoding.encode(text))
    else:
        def estimate_tokens(text): return len(text.split()) * 1.3
        
    for r in rows:
        turn = f"Question: {r['question']}\nAnswer: {r['answer']}"
        est_tokens = estimate_tokens(turn)
        context.append(turn)
        current_tokens += est_tokens
        while current_tokens > max_tokens and context:
            removed_turn = context.pop(0)
            current_tokens -= estimate_tokens(removed_turn)
        
    return context

def get_session_history(session_id: str) -> List[Tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT timestamp, category, question, answer FROM interactions WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        return cursor.fetchall()

# Initialize upon import
init_db()
