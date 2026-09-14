import sqlite3
import threading
import os
from contextlib import contextmanager

# Get the absolute path to the database file
db_name = "test.db" if os.environ.get("TESTING") == "True" else "store.db"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_name)

# Global lock for concurrent database operations that require it
db_lock = threading.Lock()

def get_connection():
    """
    Returns a SQLite connection with WAL mode enabled.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db_cursor():
    """
    Context manager for getting a database cursor.
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute(...)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@contextmanager
def get_db_connection():
    """
    Context manager for getting a database connection directly.
    """
    conn = get_connection()
    try:
        yield conn
        # Commit handled by caller or context
    finally:
        conn.close()
