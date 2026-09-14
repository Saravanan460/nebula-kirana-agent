# Nebula Kirana Operations Agent

This project implements a conversational AI agent to run an Indian kirana (grocery) store end-to-end via Telegram, as per the Nebula KnowLab Engineering Hiring Task.

## 🛠️ Architecture & Harness Choice

**Harness Picked:** `pydantic-ai`
I chose `pydantic-ai` because it offers a clean, modern, and Python-native way to build agents without the overhead of heavy node-based state machines (like LangGraph). It satisfies the requirement for a modern agent SDK while allowing true LLM orchestration. 
- **Agent-First**: The agent observes the user's message, reasons over available tools, executes them, and returns a natural language response.
- **Dynamic Context**: The `RunContext` is used to inject the `chat_id`, Telegram `message_id` (for idempotency), and the owner's persistent preferences directly into the system prompt at runtime.

**Models Used:**
- Primary: **Groq (`llama-3.3-70b-versatile`)** - Extremely fast tool-calling performance.
- Fallback: **Google Gemini (`gemini-1.5-flash`)** - Reliable free-tier model.

**Database:**
- SQLite with `WAL` (Write-Ahead Logging) mode enabled to allow concurrent reads and writes, ensuring data integrity during parallel operations.

## 🧠 Handling the "Hard Parts"

### 1. Grounding (No hallucination)
The system prompt strictly forbids guessing prices, stock, or GST rates. The LLM must call `search_product` to find real SKUs and their details, and then pass those exact SKUs into the billing and inventory tools. 

### 2. Oversell Guard
Stock validation happens entirely in the tool/database layer, not the prompt. 
- `add_item_to_bill` checks `stock_qty >= quantity` before adding an item to the draft.
- `finalize_bill` re-checks the stock for *all items in the cart* immediately before the atomic stock decrement. If any item is short, the transaction is rolled back and an error is returned to the LLM.

### 3. GST Correctness
GST calculations (CGST/SGST split, rounding) are strictly handled in Python (`calculate_gst` in `tools/billing.py`). Every product has an HSN code and tax slab stored in SQLite. The LLM never computes taxes. The generated PDF invoice includes the itemized GST breakup as required by Indian law.

### 4. Multi-turn Bills
A `bills` table tracks bills in a `draft` state. `add_item_to_bill` and `edit_bill_item` modify the draft. Draft bills **do not** decrement stock. Only when `finalize_bill` is called does the system lock the bill and decrement the inventory.

### 5. Idempotency (Telegram Redeliveries)
The Telegram bot passes the unique `update.message.message_id` to the agent, which uses it as the `txn_id` when calling `finalize_bill`. 
The `finalize_bill` tool does an atomic `SAVEPOINT check_txn` query. If the `txn_id` already exists, it returns a success message without double-billing or double-decrementing stock.

### 6. Concurrency
- **SQLite WAL Mode**: Enabled on startup to allow better concurrent access.
- **`BEGIN IMMEDIATE`**: Used in all stock-modifying and billing finalization queries to serialize writes.
- **Atomic Decrement**: `UPDATE products SET stock_qty = stock_qty - ? WHERE stock_qty >= ?` ensures that race conditions between the `SELECT` check and the `UPDATE` cannot result in negative stock.

### 7. Real Artifacts
- **PDF Invoices**: Generated using `reportlab`. Pulls finalized bill data from SQLite, formats it as a Tax Invoice with HSN codes, SGST/CGST columns, and totals.
- **PPTX Decks**: Generated using `python-pptx`. Queries SQLite for top-selling items and payment mode breakdowns, inserting native clustered column and pie charts into the slide deck.

### 8. Memory Across Sessions
- `tools/preferences.py` saves user preferences (e.g., default payment mode) into a SQLite `preferences` table.
- When `/new` is called, the Telegram bot clears the in-memory chat history (giving the LLM a blank slate) but the persistent SQLite preferences remain. These are injected into the system prompt on every new message, ensuring the store "remembers" how the owner works.

## 🚀 How to Run

1. Clone this repository.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   ```
3. Set up the `.env` file with your API keys:
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   GROQ_API_KEY=your_key
   GEMINI_API_KEY=your_key (fallback)
   ```
4. Run the application:
   ```bash
   python main.py
   ```
   *(This will automatically initialize and seed the SQLite database if it doesn't exist, and start the Telegram bot).*

5. Use **Ngrok** or **Cloudflare Tunnels** to expose your local bot if required by your setup, though python-telegram-bot's `run_polling()` works fine locally without webhooks for testing.

---
**Prepared for Nebula KnowLab Engineering Task**
