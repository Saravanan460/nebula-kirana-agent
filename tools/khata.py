from database.connection import get_db_cursor, db_lock

def create_khata(chat_id: int, customer_name: str) -> str:
    """Create a new khata (credit ledger) for a customer."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO khata (chat_id, customer) VALUES (?, ?)", 
                (chat_id, customer_name)
            )
            return f"✅ Khata created for customer '{customer_name}'."
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            return f"❌ Error: Khata for '{customer_name}' already exists."
        return f"❌ Error creating khata: {str(e)}"

def charge_khata(chat_id: int, customer_name: str, amount: float, note: str = "") -> str:
    """Add a manual charge to a customer's khata."""
    if amount <= 0:
        return "❌ Error: Amount must be positive."
        
    with db_lock:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, balance FROM khata WHERE chat_id = ? AND customer = ?", (chat_id, customer_name))
            row = cursor.fetchone()
            if not row:
                return f"❌ Error: Khata for '{customer_name}' not found. Create it first."
                
            khata_id = row['id']
            new_balance = row['balance'] + amount
            
            cursor.execute("UPDATE khata SET balance = ? WHERE id = ?", (new_balance, khata_id))
            cursor.execute(
                "INSERT INTO khata_txns (khata_id, amount, note) VALUES (?, ?, ?)",
                (khata_id, amount, note or "Manual charge")
            )
            return f"✅ Charged ₹{amount} to {customer_name}. New balance: ₹{new_balance} (Owed to you)."

def pay_khata(chat_id: int, customer_name: str, amount: float, note: str = "") -> str:
    """Record a payment received from a khata customer."""
    if amount <= 0:
        return "❌ Error: Amount must be positive."
        
    with db_lock:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, balance FROM khata WHERE chat_id = ? AND customer = ?", (chat_id, customer_name))
            row = cursor.fetchone()
            if not row:
                return f"❌ Error: Khata for '{customer_name}' not found."
                
            khata_id = row['id']
            current_balance = row['balance']
            
            if amount > current_balance:
                return f"❌ Error: Cannot pay ₹{amount}. {customer_name} only owes ₹{current_balance}."
                
            new_balance = current_balance - amount
            
            cursor.execute("UPDATE khata SET balance = ? WHERE id = ?", (new_balance, khata_id))
            cursor.execute(
                "INSERT INTO khata_txns (khata_id, amount, note) VALUES (?, ?, ?)",
                (khata_id, -amount, note or "Payment received")
            )
            return f"✅ Recorded payment of ₹{amount} from {customer_name}. Remaining balance: ₹{new_balance}."

def check_khata(chat_id: int, customer_name: str = None) -> str:
    """
    Check balance for a specific customer or list all khatas with a balance.
    """
    with get_db_cursor() as cursor:
        if customer_name:
            cursor.execute("SELECT id, balance FROM khata WHERE chat_id = ? AND customer = ?", (chat_id, customer_name))
            row = cursor.fetchone()
            if not row:
                return f"❌ Error: Khata for '{customer_name}' not found."
                
            cursor.execute(
                "SELECT amount, note, created_at FROM khata_txns WHERE khata_id = ? ORDER BY created_at DESC LIMIT 5",
                (row['id'],)
            )
            txns = cursor.fetchall()
            
            res = f"📒 {customer_name}'s Khata\n"
            res += f"Current Balance: ₹{row['balance']} (Owed to you)\n\n"
            res += "Recent Transactions:\n"
            for t in txns:
                date_str = t['created_at'].split()[0]
                amount_str = f"+₹{t['amount']}" if t['amount'] > 0 else f"-₹{abs(t['amount'])}"
                res += f"{date_str}: {amount_str} ({t['note']})\n"
            return res
        else:
            cursor.execute("SELECT customer, balance FROM khata WHERE chat_id = ? AND balance > 0", (chat_id,))
            rows = cursor.fetchall()
            if not rows:
                return "✅ No outstanding khatas."
                
            res = "📒 All Active Khatas:\n"
            total = 0
            for r in rows:
                res += f"- {r['customer']}: ₹{r['balance']}\n"
                total += r['balance']
            res += f"\nTotal money out in the market: ₹{total}"
            return res
