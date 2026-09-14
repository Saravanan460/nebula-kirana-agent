from database.connection import get_db_cursor

def set_preference(chat_id: int, key: str, value: str) -> str:
    """Set a preference for the owner (e.g. default_payment=upi, default_atta=aashirvaad 5kg)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO preferences (chat_id, key, value) 
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, key) DO UPDATE SET value = excluded.value
            """,
            (chat_id, key.lower(), value)
        )
        return f"✅ Preference '{key}' set to '{value}'."

def get_preferences(chat_id: int) -> dict:
    """Get all preferences for a chat (used to build system prompt)."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT key, value FROM preferences WHERE chat_id = ?", (chat_id,))
        rows = cursor.fetchall()
        return {r['key']: r['value'] for r in rows}

def clear_conversation_memory(chat_id: int) -> str:
    """
    Clears the active bill draft if any. 
    (Note: LLM conversation history clearing is handled at the harness level).
    """
    with get_db_cursor() as cursor:
        cursor.execute("UPDATE bills SET status = 'cancelled' WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        return "✅ Memory cleared. Drafts cancelled. Start fresh."
