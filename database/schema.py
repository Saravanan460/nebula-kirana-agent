import os
import sqlite3
from database.connection import get_connection

SCHEMA_SQL = """
-- Products / Inventory
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,              -- "Aashirvaad Atta 5kg"
    sku         TEXT NOT NULL,              -- "AASH-ATTA-5KG"
    hsn_code    TEXT NOT NULL,              -- "1101" 
    unit        TEXT NOT NULL DEFAULT 'packet', -- kg/g/litre/ml/packet/dozen/piece
    is_loose    BOOLEAN NOT NULL DEFAULT 0, -- loose items sold by weight
    cost_price  REAL NOT NULL,             -- what owner paid (₹)
    mrp         REAL NOT NULL,             -- sell price (₹)
    gst_rate    REAL NOT NULL DEFAULT 0.0, -- 0, 5, 12, 18 (percentage)
    stock_qty   REAL NOT NULL DEFAULT 0,   -- current stock (can be fractional for loose)
    reorder_level REAL NOT NULL DEFAULT 10,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   BOOLEAN NOT NULL DEFAULT 1, -- soft delete only, never hard delete
    UNIQUE(chat_id, sku)
);

-- Bills (multi-turn draft -> finalized)
CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         INTEGER NOT NULL,          -- Telegram chat ID
    status          TEXT NOT NULL DEFAULT 'draft', -- draft | finalized | cancelled
    payment_mode    TEXT,                       -- cash / upi / card
    payment_ref     TEXT,                       -- UPI ref, card last-4, etc.
    subtotal        REAL DEFAULT 0,
    total_cgst      REAL DEFAULT 0,
    total_sgst      REAL DEFAULT 0,
    grand_total     REAL DEFAULT 0,
    txn_id          TEXT UNIQUE,                -- idempotency key (UUID)
    khata_customer  TEXT,                       -- if on credit, whose khata
    customer_name   TEXT,                       -- buyer's name (always required)
    reviewed        INTEGER NOT NULL DEFAULT 0, -- 1 = owner has seen the bill via view_bill
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at    TIMESTAMP
);

-- Bill Line Items
CREATE TABLE IF NOT EXISTS bill_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id     INTEGER NOT NULL REFERENCES bills(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    REAL NOT NULL,
    unit_price  REAL NOT NULL,             -- price per unit at time of billing
    gst_rate    REAL NOT NULL,
    cgst        REAL NOT NULL DEFAULT 0,
    sgst        REAL NOT NULL DEFAULT 0,
    line_total  REAL NOT NULL DEFAULT 0,   -- (unit_price * qty) + cgst + sgst
    UNIQUE(bill_id, product_id)            -- one line per product per bill
);

-- Khata (Credit Ledger)
CREATE TABLE IF NOT EXISTS khata (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer    TEXT NOT NULL,
    chat_id     INTEGER NOT NULL,
    balance     REAL NOT NULL DEFAULT 0,    -- positive = customer owes store
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, customer)
);

-- Khata Transactions (audit trail)
CREATE TABLE IF NOT EXISTS khata_txns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    khata_id    INTEGER NOT NULL REFERENCES khata(id),
    bill_id     INTEGER REFERENCES bills(id),
    amount      REAL NOT NULL,             -- positive = charge, negative = payment
    note        TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Owner Preferences (persist across /new)
CREATE TABLE IF NOT EXISTS preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    key         TEXT NOT NULL,              -- "default_payment", "default_atta", "shop_name", "gstin"
    value       TEXT NOT NULL,
    UNIQUE(chat_id, key)
);

-- Daily Close Snapshots
CREATE TABLE IF NOT EXISTS daily_close (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    close_date  DATE NOT NULL,
    total_sales REAL NOT NULL,
    total_cgst  REAL NOT NULL,
    total_sgst  REAL NOT NULL,
    cash_total  REAL NOT NULL,
    upi_total   REAL NOT NULL,
    card_total  REAL NOT NULL,
    bills_count INTEGER NOT NULL,
    top_items   TEXT,                       -- JSON array of top selling items
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, close_date)
);
"""

def setup_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print("Database schema created successfully.")
        # Safe migration: add customer_name column if it doesn't exist yet
        try:
            conn.execute("ALTER TABLE bills ADD COLUMN customer_name TEXT")
            conn.commit()
            print("Migration: added customer_name column to bills.")
        except Exception:
            pass  # Column already exists — that's fine
        # Safe migration: add reviewed column if it doesn't exist yet
        try:
            conn.execute("ALTER TABLE bills ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0")
            conn.commit()
            print("Migration: added reviewed column to bills.")
        except Exception:
            pass  # Column already exists — that's fine
    except Exception as e:
        print(f"Error creating schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_db()
