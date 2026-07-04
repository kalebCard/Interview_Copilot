import sqlite3
from pathlib import Path
import time
from typing import List, Tuple
from copilot.core.config import PROJECT_ROOT

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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO interactions (session_id, timestamp, category, question, answer) VALUES (?, ?, ?, ?, ?)",
            (session_id, time.time(), category, question, answer)
        )

def get_recent_context(session_id: str, max_tokens: int = 2000) -> List[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT question, answer FROM interactions WHERE session_id = ? ORDER BY timestamp DESC",
            (session_id,)
        )
        rows = cursor.fetchall()
        
    context: List[str] = []
    current_tokens: float = 0.0
    for q, a in rows:
        turn = f"Question: {q}\nAnswer: {a}"
        est_tokens = len(turn.split()) * 1.3
        if current_tokens + est_tokens > max_tokens:
            break
        context.insert(0, turn)
        current_tokens += est_tokens
        
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
