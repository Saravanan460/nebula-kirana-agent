# 🛒 Nebula Kirana Operations Agent

<div align="center">
  <h3>Run an entire Indian kirana store from a chat window — with an agent, not a menu.</h3>
  <i>An autonomous, conversational Point-of-Sale (POS) and store management agent built for Indian Kirana stores.</i><br><br>
  <b>🤖 Live Bot: <a href="https://t.me/NebulaKirana_Saravanan_bot">@NebulaKirana_Saravanan_bot</a></b><br>
  <b>Developed for the Nebula KnowLab Engineering Hiring Task</b>
</div>

---

## 🌟 Overview

The **Nebula Kirana Agent** completely replaces complex POS software. The store owner runs their entire shop simply by chatting with this agent on Telegram — no menus, no forms, no admin panel. The chat *is* the product.

- 📦 **Inventory Management** — add products, receive stock, search, low-stock alerts, list entire inventory
- 🧾 **GST-Compliant Billing** — multi-item draft bills, mid-build edits, finalization with tax breakup
- 📒 **Khata (Credit Ledger)** — create customer credit, charge bills, record payments, check balances
- 📊 **Analytics & Documents** — PDF invoices (reportlab) & Weekly PPTX sales decks (python-pptx) with real charts
- 🧠 **Persistent Memory** — owner preferences survive `/new` chat resets
- 🏢 **Multi-Tenant** — every Telegram user gets a completely isolated private store sandbox

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        TELEGRAM USER                             │
│            "make a bill: 2kg sugar, 4 maggi, UPI"                │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   TELEGRAM BOT LAYER                             │
│  handlers.py — routes /start, /new, and natural language msgs    │
│  Maintains per-chat conversation history (last 20 messages)      │
│  Converts **bold** → <b>HTML</b> for clean Telegram rendering   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                  PYDANTIC-AI AGENT (harness.py)                  │
│                                                                  │
│  ┌─────────────┐    The LLM receives the user's natural          │
│  │  Groq API   │    language, reasons over it, and decides       │
│  │ (gpt-oss)   │    which tools to call. It chains multiple      │
│  │     or      │    tool calls in a single turn as needed.       │
│  │ Gemini 2.0  │    Business rules live in the TOOLS,            │
│  │  (fallback) │    not the prompt.                              │
│  └─────────────┘                                                 │
│                                                                  │
│  System Prompt dynamically injects owner preferences             │
│  from SQLite on every single message.                            │
└──────────────────────┬───────────────────────────────────────────┘
                       │ Calls tools based on reasoning
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     TOOL / SKILL LAYER                           │
│                                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │ inventory  │ │  billing   │ │   khata    │ │ preferences  │  │
│  │            │ │            │ │            │ │              │  │
│  │ add_product│ │ start_bill │ │create_khata│ │set_preference│  │
│  │recv_stock  │ │ add_item   │ │charge_khata│ │get_preference│  │
│  │check_stock │ │ edit_item  │ │ pay_khata  │ │              │  │
│  │search      │ │ view_bill  │ │check_khata │ │              │  │
│  │list_all    │ │ finalize   │ │            │ │              │  │
│  │low_stock   │ │ cancel     │ │            │ │              │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
│                                                                  │
│  ┌────────────┐ ┌──────────────────────────────────────────────┐ │
│  │ analytics  │ │           documents                          │ │
│  │            │ │                                              │ │
│  │daily_sum   │ │ generate_invoice_pdf  (reportlab)            │ │
│  │close_day   │ │ generate_analysis_pptx (python-pptx + charts)│ │
│  └────────────┘ └──────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────────────────┘
                       │ All tools enforce business rules
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   SQLite DATABASE (WAL mode)                     │
│                                                                  │
│  ┌──────────┐ ┌───────┐ ┌───────────┐ ┌───────┐ ┌───────────┐  │
│  │ products │ │ bills │ │bill_items │ │ khata │ │preferences│  │
│  │(per user)│ │       │ │           │ │       │ │           │  │
│  └──────────┘ └───────┘ └───────────┘ └───────┘ └───────────┘  │
│                                                                  │
│  Every table is scoped by chat_id → full multi-tenant isolation  │
│  Data survives restarts. /new clears context, not the database.  │
└──────────────────────────────────────────────────────────────────┘
```

### Control Loop

The agent follows a strict **Observe → Reason → Act → Feed Back** loop:

```
User: "make a bill: 2kg sugar and 4 maggi, UPI"
  │
  ├─→ LLM reasons: "I need SKUs. Let me search first."
  │     ├─→ TOOL CALL: search_product("sugar")     → finds SUGAR-LOOSE
  │     ├─→ TOOL CALL: search_product("maggi")     → finds MAGGI-70G
  │     ├─→ TOOL CALL: start_bill()                → draft created
  │     ├─→ TOOL CALL: add_item("SUGAR-LOOSE", 2)  → ✅ added
  │     ├─→ TOOL CALL: add_item("MAGGI-70G", 4)    → ✅ added
  │     └─→ TOOL CALL: finalize_bill("upi")        → ✅ stock decremented
  │
  └─→ Agent replies: "Bill finalized! Total ₹146 via UPI."
```

> **No regex router, no if/elif branches.** The LLM decides which tools to call and chains them autonomously.

---

## 🛠️ The 100% Free Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **Agent Harness** | `pydantic-ai` | Clean, type-safe, agent-first — no LangGraph-style node boilerplate |
| **LLM Engine** | `Groq API` (gpt-oss-120b) | Lightning-fast tool-calling; fallback to `Gemini 2.0 Flash` |
| **Database** | `SQLite` (WAL mode) | Built into Python, free, durable, handles concurrency |
| **Interface** | `Telegram Bot API` | Zero cost, file sharing (PDF/PPTX), accessible to shopkeepers |
| **PDF Generation** | `reportlab` | Offline GST-compliant invoice generation |
| **PPTX Generation** | `python-pptx` | Native charts and slides for business analysis decks |
| **Hosting** | `PythonAnywhere` | Free 24/7 cloud hosting for the live bot |

---

## 🧠 Engineering Solutions to the "Hard Parts"

We didn't just build a chatbot; we built a rigorous, stateful backend application orchestrated by an LLM. Every "hard part" from the assignment is addressed below.

### 🛡️ 1. Grounding & Oversell Guard
> *"Prices, GST slabs and stock come from the DB via tools. Never invent a product or a price."*

The LLM is strictly forbidden from guessing SKUs, prices, or taxes. It **must** use `search_product` to fetch reality from the database.

- **Oversell Guard:** Stock validation happens entirely in the **tool/database layer**, not the prompt. If the user asks for 300 packets but only 150 exist, `add_item_to_bill` explicitly blocks it and returns an error.
- **Below-Cost Guard:** `finalize_bill` checks that no item's MRP is below its `cost_price`.
- **Off-Topic Resistance:** The agent refuses non-store requests like "write me a Python script" — it stays in character as a store operator.

### 🔄 2. Concurrency & Race Conditions
> *"Two bills — or a sale plus a stock-in — in flight at once must not corrupt stock."*

- **WAL Mode:** Enabled on SQLite startup for concurrent read/writes.
- **`BEGIN IMMEDIATE`:** Locks the database during critical stock modifications.
- **Atomic Decrement:** `UPDATE products SET stock_qty = stock_qty - ? WHERE stock_qty >= ?` is the absolute final guard against negative stock.

### 🧾 3. Idempotency (No Double-Billing)
> *"Telegram redelivers updates. A retried 'finalize' must not double-bill."*

- The Telegram `message_id` is passed into `AgentDeps` and used as a unique `txn_id`.
- `finalize_bill` enforces a `UNIQUE(txn_id)` constraint via `SAVEPOINT`. If the same message triggers finalization twice, it is silently ignored.

### 💬 4. Stateful Multi-Turn Bills
> *"A bill builds over several messages, supports edits, and only decrements stock on finalize."*

The `bills` table tracks active drafts. `add_item_to_bill` and `edit_bill_item` modify the draft without touching inventory. Stock is only decremented atomically when `finalize_bill` is called.

### 📊 5. Real Artifact Generation
> *"A proper GST invoice (PDF) and a business-analysis deck (PPTX) with real charts."*

- **PDF Invoices (`reportlab`):** Pulls finalized bill data from SQLite, formats it as a standard Tax Invoice with HSN codes and SGST/CGST split.
- **Weekly Decks (`python-pptx`):** Queries SQLite for top-selling items and payment mode breakdowns, renders native clustered column charts and pie charts.

### 🧠 6. Durable Memory Across Sessions
> *"Standing preferences persist across chats — start a /new chat and they still apply."*

- Preferences (e.g., `"always assume UPI"`, `"my default atta is Aashirvaad 5kg"`) are saved to a durable `preferences` table.
- `/new` wipes conversation context but preferences are dynamically injected into the system prompt on every message. The agent *truly remembers*.

### 🏢 7. Multi-Tenant Sandbox Architecture
> *"A live bot we can message — deploy it and put the Telegram bot handle in your README."*

Multiple Nebula engineers can test simultaneously without collision:
- The entire database — `products`, `bills`, `khata`, `preferences` — is strictly isolated by `chat_id`.
- **Auto-Seeding:** The moment a reviewer hits `/start`, their private store is pre-seeded with all mandatory SKUs (Atta, Maggi, Salt, Butter, Oil, etc.).

### ✅ 8. GST Correctness
> *"Per-item slab, CGST/SGST split, rounding, and a legible tax breakup on the bill."*

- Each product carries its own `gst_rate` (0%, 5%, 12%, 18%) and `hsn_code`.
- MRP is treated as GST-inclusive (standard Indian retail). The tool back-calculates base amount, splits into CGST + SGST, and rounds correctly.
- Every bill shows a per-line and total tax breakup.

---

## 📋 Capability Map (from Assignment §3)

| Intent | Example Message | Status |
|--------|----------------|--------|
| Receive stock | *"50 packets of Maggi came in, cost ₹12, MRP ₹14"* | ✅ |
| Add a new product | *"new item: Amul Butter 100g, GST 12%, MRP ₹62"* | ✅ |
| Cut a bill | *"make a bill: 2kg sugar, 1 atta 5kg, 4 Maggi, UPI"* | ✅ |
| Edit a bill mid-build | *"drop the butter, make it 6 Maggi"* | ✅ |
| Stock query | *"how much sugar is left?"* | ✅ |
| Low-stock / reorder | *"what's running out?"* | ✅ |
| List all inventory | *"what products do we have?"* | ✅ |
| Credit (khata) | *"put ₹500 on Ramesh's credit"* / *"Ramesh paid ₹300"* | ✅ |
| Daily close | *"today's sales?"* / *"close the day"* | ✅ |
| Invoice as PDF | *"send me that bill as a PDF"* | ✅ |
| Analysis deck | *"make this week's sales analysis deck"* | ✅ |
| Set a preference | *"always assume UPI unless I say cash"* | ✅ |
| Ambiguity handling | *"add atta"* → "Which one — Aashirvaad 5kg or loose?" | ✅ |

---

## 🚀 Getting Started

### 1. Clone & Setup
```bash
git clone https://github.com/Saravanan460/nebula-kirana-agent.git
cd nebula-kirana-agent
python -m venv venv
source venv/bin/activate        # Linux/Mac
# .\venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Run the Agent
```bash
python main.py
```
> The bot automatically initializes the database schema and starts Telegram polling. Each new user's store is auto-seeded with the mandatory SKUs on `/start`.

### 4. Start Chatting!
Open Telegram → search for your bot → send `/start` → your private store is ready!

---

## 🗂️ Project Structure

```
nebula-kirana-agent/
├── main.py                    # Entry point — loads env, inits DB & agent, starts bot
├── agent/
│   ├── harness.py             # Pydantic-AI agent, model selection, all 18 tool registrations
│   └── prompts.py             # Dynamic system prompt with injected preferences
├── database/
│   ├── connection.py          # SQLite connection pool with WAL mode & threading lock
│   ├── schema.py              # CREATE TABLE statements (all scoped by chat_id)
│   └── seed_data.py           # Auto-seeds 12 mandatory SKUs per user
├── telegram_bot/
│   ├── bot.py                 # Telegram Application setup & polling
│   └── handlers.py            # /start, /new, message routing, HTML formatting
├── tools/
│   ├── inventory.py           # add, receive, check, search, list, low-stock
│   ├── billing.py             # start, add, edit, view, finalize, cancel (with guards)
│   ├── khata.py               # create, charge, pay, check credit ledger
│   ├── preferences.py         # set/get persistent owner preferences
│   ├── documents.py           # PDF invoice (reportlab) & PPTX deck (python-pptx)
│   └── analytics.py           # daily_summary, close_day
├── artifacts/                 # Generated PDFs and PPTXs are saved here
├── requirements.txt
└── .env
```

---

*Built with ❤️ by Saravana for Nebula KnowLab*
