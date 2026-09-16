# Side-channel for file delivery. Tools append file paths here;
# the Telegram handler pops them after agent.run() completes.
# Keyed by chat_id so concurrent chats don't collide.

PENDING_FILES: dict[int, list[str]] = {}


def queue_file(chat_id: int, file_path: str):
    """Queue a generated file to be sent to the user after the agent responds."""
    if chat_id not in PENDING_FILES:
        PENDING_FILES[chat_id] = []
    PENDING_FILES[chat_id].append(file_path)


def pop_files(chat_id: int) -> list[str]:
    """Pop and return all pending files for a chat_id."""
    return PENDING_FILES.pop(chat_id, [])
