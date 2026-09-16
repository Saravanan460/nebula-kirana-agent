# 🛒 Nebula Kirana Operations Agent

<div align="center">
  <i>An autonomous, conversational Point-of-Sale (POS) and store management agent built for Indian Kirana stores.</i><br>
  <b>Developed for the Nebula KnowLab Engineering Hiring Task</b>
</div>

---

## 🌟 Overview

The **Nebula Kirana Agent** completely replaces complex POS software. The store owner runs their entire shop simply by chatting with this agent on Telegram. It handles:
- **Inventory Management** (tracking stock, low-stock alerts, listing all products)
- **GST-Compliant Billing** (multi-item drafts, edits, finalization)
- **Khata Ledger** (managing customer credit, manual charges, and payments)
- **Analytics & Documents** (generating PDF invoices and Weekly PPTX Sales Decks)

## 🛠️ The 100% Free Tech Stack

This project was built strictly adhering to the requirement of using a completely free, durable, and highly capable technology stack:

- **Harness:** `pydantic-ai` 🧠
  - *Why?* Provides a clean, modern, type-safe, agent-first approach without the heavy boilerplate of rigid node-based state machines (like LangGraph).
- **LLM Engine:** `Groq API` ⚡
  - *Why?* Lightning-fast tool-calling (Llama 3 / GPT-OSS) allowing the agent to perform multi-step database updates gracefully. (Fallback to `Gemini 1.5 Flash`).
- **Database:** `SQLite` 🗄️
  - *Why?* Built directly into Python, completely free, and configured with `WAL` (Write-Ahead Logging) to provide a durable memory that survives restarts and handles concurrency flawlessly.
- **Interface:** `Telegram Bot API` 💬
  - *Why?* Zero cost, natively supports file sharing (PDF/PPTX), and extremely accessible for small business owners.

---

## 🧠 Engineering Solutions to the "Hard Parts"

We didn't just build a chatbot; we built a rigorous, stateful backend application orchestrated by an LLM.

### 🛡️ 1. Oversell Guard & Grounding
The LLM is strictly forbidden from guessing SKUs, prices, or taxes. It must use the `search_product` tool to fetch reality. 
- **The Guard:** Stock validation happens entirely in the tool/database layer, not the prompt. If the user asks for 300 packets but only 150 exist, the `add_item_to_bill` tool explicitly blocks it and returns an error back to the LLM to inform the user.
- **Below-Cost Guard:** `finalize_bill` strictly checks that no item is sold below its `cost_price`.

### 🔄 2. Concurrency & Race Conditions
- **WAL Mode:** Enabled on SQLite startup for concurrent read/writes.
- **`BEGIN IMMEDIATE`:** Used to lock the database during critical stock modifications.
- **Atomic Decrement:** The query `UPDATE products SET stock_qty = stock_qty - ? WHERE stock_qty >= ?` acts as an absolute final guard against race conditions that could lead to negative stock.

### 🧾 3. Idempotency (Preventing Double-Billing)
Network glitches or users tapping buttons twice shouldn't result in double-billing.
- The Telegram `message_id` is passed into the `AgentDeps` context and used as a unique `txn_id`.
- The `finalize_bill` tool enforces a `UNIQUE(txn_id)` constraint via a `SAVEPOINT` query. If the same message triggers finalization twice, it is silently ignored, preventing double-decrementing of stock or double-charging.

### 💬 4. Stateful Multi-Turn Bills
Users change their minds. The `bills` table tracks active drafts. 
Tools like `add_item_to_bill` and `edit_bill_item` modify this draft without touching inventory. Stock is only ever decremented when `finalize_bill` is explicitly called.

### 📊 5. Real Artifact Generation
The LLM orchestrates the creation of real files using Python libraries, completely offline:
- **PDF Invoices (`reportlab`)**: Pulls finalized bill data from SQLite, formatting it as a standard Tax Invoice with correct HSN codes and SGST/CGST split calculations.
- **Weekly Decks (`python-pptx`)**: Queries the SQLite database for top-selling items and payment mode breakdowns, rendering native clustered column charts and pie charts into a slide deck.

### 🧠 6. Durable Memory Across Sessions
- User preferences (e.g., `"always assume UPI"`, `"my default atta is Aashirvaad 5kg"`) are parsed by the agent and saved to a durable `preferences` table.
- When the chat is cleared via `/new`, the short-term conversation context is wiped, but the persistent SQLite preferences are dynamically injected into the system prompt on every new message. The agent *truly remembers* the owner's habits across sessions.

### 🏢 7. Multi-Tenant Sandbox Architecture (Perfect for Reviewers)
The assignment requires a live bot that multiple Nebula engineers can test simultaneously. If the inventory was completely global, reviewers testing stock decrements would collide and corrupt each other's test state. 
- **The Solution:** The entire database schema—including `products` (inventory), `bills`, `khata`, and `preferences`—is strictly isolated by Telegram `chat_id`. 
- **Auto-Seeding:** The moment a reviewer hits `/start`, their completely private store is instantly pre-seeded with the exact mandatory assignment SKUs (Aashirvaad Atta, Maggi, Tata Salt, etc.). Every reviewer gets a flawless, interference-free grading sandbox.

---

## 🚀 Getting Started

1. **Clone & Setup:**
   ```bash
   git clone https://github.com/Saravanan460/nebula-kirana-agent.git
   cd nebula-kirana-agent
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GROQ_API_KEY=your_groq_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. **Run the Agent:**
   ```bash
   python main.py
   ```
   *Note: This will automatically initialize the database, seed it with initial products, and start the Telegram bot via polling.*

4. **Start Chatting!**
   Open your Telegram bot and send `/start`.

---
*Developed by Saravana for Nebula.*
