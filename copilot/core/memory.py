import sqlite3
import threading
import time
from typing import List, Tuple
from copilot.core.paths import DB_PATH
from copilot.core.logger import get_logger


logger = get_logger(__name__)

_db_initialized = False
_db_lock = threading.Lock()

def init_db():
    global _db_initialized
    with _db_lock:
        if _db_initialized:
            return
        _db_initialized = True
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
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
        logger.error(f"Error guardando interacción: {e}")

def get_recent_context(session_id: str, max_tokens: int = 1500) -> List[str]:
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT question, answer FROM interactions WHERE session_id = ? ORDER BY timestamp ASC LIMIT 100",
                (session_id,)
            )
            rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Error al leer contexto: {e}")
        return []
        
    context: List[str] = []
    current_tokens: float = 0.0
    
    def estimate_tokens(text: str) -> float:
        return len(text.split()) * 1.3

        
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

