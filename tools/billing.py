from database.connection import get_db_cursor, db_lock
import uuid
from datetime import datetime

def calculate_gst(mrp_total: float, gst_rate: float) -> tuple[float, float, float]:
    """Returns (cgst, sgst, total_with_tax). In India, MRP is inclusive of GST."""
    base_amount = mrp_total / (1 + (gst_rate / 100))
    gst_amount = mrp_total - base_amount
    cgst = round(gst_amount / 2, 2)
    sgst = round(gst_amount / 2, 2)
    return cgst, sgst, round(mrp_total, 2)

def start_bill(chat_id: int) -> str:
    """Start a new draft bill for the chat. Cancels any existing draft."""
    with get_db_cursor() as cursor:
        # Cancel any existing draft
        cursor.execute("UPDATE bills SET status = 'cancelled' WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        
        # Create new draft
        cursor.execute("INSERT INTO bills (chat_id, status) VALUES (?, 'draft')", (chat_id,))
        bill_id = cursor.lastrowid
        return f"✅ Started new draft bill (ID: {bill_id}). You can now add items."

def add_item_to_bill(chat_id: int, sku: str, quantity: float) -> str:
    """Add a product to the current draft bill."""
    if quantity <= 0:
        return "❌ Error: Quantity must be positive."
        
    with get_db_cursor() as cursor:
        # Get draft bill
        cursor.execute("SELECT id FROM bills WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        bill_row = cursor.fetchone()
        if not bill_row:
            return "❌ Error: No active draft bill. Start a bill first."
        bill_id = bill_row['id']
        
        # Get product and verify stock
        cursor.execute("SELECT id, name, mrp, gst_rate, stock_qty FROM products WHERE sku = ? AND is_active = 1", (sku,))
        prod_row = cursor.fetchone()
        if not prod_row:
            return f"❌ Error: Product with SKU '{sku}' not found."
            
        if prod_row['stock_qty'] < quantity:
            return f"❌ Error: Guardrail blocked - Oversell. '{prod_row['name']}' has only {prod_row['stock_qty']} in stock, requested {quantity}."
            
        # Calculate line item details
        base_line_total = prod_row['mrp'] * quantity
        cgst, sgst, line_total = calculate_gst(base_line_total, prod_row['gst_rate'])
        
        # Upsert line item (if already exists, just add quantity)
        cursor.execute("SELECT id, quantity FROM bill_items WHERE bill_id = ? AND product_id = ?", (bill_id, prod_row['id']))
        item_row = cursor.fetchone()
        
        if item_row:
            new_qty = item_row['quantity'] + quantity
            if prod_row['stock_qty'] < new_qty:
                return f"❌ Error: Guardrail blocked - Oversell. '{prod_row['name']}' has only {prod_row['stock_qty']} in stock, total in bill would be {new_qty}."
            
            new_base = prod_row['mrp'] * new_qty
            n_cgst, n_sgst, n_line_total = calculate_gst(new_base, prod_row['gst_rate'])
            
            cursor.execute(
                """
                UPDATE bill_items 
                SET quantity = ?, cgst = ?, sgst = ?, line_total = ? 
                WHERE id = ?
                """,
                (new_qty, n_cgst, n_sgst, n_line_total, item_row['id'])
            )
            return f"✅ Updated '{prod_row['name']}' in bill to {new_qty}."
        else:
            cursor.execute(
                """
                INSERT INTO bill_items (bill_id, product_id, quantity, unit_price, gst_rate, cgst, sgst, line_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bill_id, prod_row['id'], quantity, prod_row['mrp'], prod_row['gst_rate'], cgst, sgst, line_total)
            )
            return f"✅ Added {quantity} of '{prod_row['name']}' to bill."

def edit_bill_item(chat_id: int, sku: str, new_quantity: float) -> str:
    """Edit the quantity of an item in the draft bill. Pass 0 to remove."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM bills WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        bill_row = cursor.fetchone()
        if not bill_row:
            return "❌ Error: No active draft bill."
        bill_id = bill_row['id']
        
        cursor.execute("SELECT id, name, mrp, gst_rate, stock_qty FROM products WHERE sku = ?", (sku,))
        prod_row = cursor.fetchone()
        if not prod_row:
            return f"❌ Error: Product with SKU '{sku}' not found."
            
        if new_quantity <= 0:
            cursor.execute("DELETE FROM bill_items WHERE bill_id = ? AND product_id = ?", (bill_id, prod_row['id']))
            return f"✅ Removed '{prod_row['name']}' from bill."
            
        if prod_row['stock_qty'] < new_quantity:
            return f"❌ Error: Guardrail blocked - Oversell. '{prod_row['name']}' has only {prod_row['stock_qty']} in stock."
            
        base_line_total = prod_row['mrp'] * new_quantity
        cgst, sgst, line_total = calculate_gst(base_line_total, prod_row['gst_rate'])
        
        cursor.execute(
            """
            UPDATE bill_items 
            SET quantity = ?, cgst = ?, sgst = ?, line_total = ? 
            WHERE bill_id = ? AND product_id = ?
            """,
            (new_quantity, cgst, sgst, line_total, bill_id, prod_row['id'])
        )
        if cursor.rowcount == 0:
            return f"❌ Error: '{prod_row['name']}' is not in the current bill."
            
        return f"✅ Updated '{prod_row['name']}' quantity to {new_quantity}."

def view_bill(chat_id: int) -> str:
    """View the current draft bill and its totals."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM bills WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        bill_row = cursor.fetchone()
        if not bill_row:
            return "📝 No active draft bill."
        bill_id = bill_row['id']
        
        cursor.execute(
            """
            SELECT p.name, b.quantity, b.unit_price, b.line_total, b.cgst, b.sgst, p.unit
            FROM bill_items b
            JOIN products p ON b.product_id = p.id
            WHERE b.bill_id = ?
            """,
            (bill_id,)
        )
        items = cursor.fetchall()
        
        if not items:
            return f"📝 Bill (ID: {bill_id}) is empty."
            
        subtotal = 0
        total_cgst = 0
        total_sgst = 0
        grand_total = 0
        
        res = f"🧾 Current Bill (ID: {bill_id})\n"
        res += "-" * 30 + "\n"
        for item in items:
            res += f"{item['name']} - {item['quantity']} {item['unit']} @ ₹{item['unit_price']}\n"
            if item['cgst'] > 0 or item['sgst'] > 0:
                res += f"   + Tax: CGST ₹{item['cgst']} | SGST ₹{item['sgst']}\n"
            res += f"   Line Total: ₹{item['line_total']}\n"
            
            subtotal += item['quantity'] * item['unit_price']
            total_cgst += item['cgst']
            total_sgst += item['sgst']
            grand_total += item['line_total']
            
        res += "-" * 30 + "\n"
        res += f"Subtotal: ₹{round(subtotal, 2)}\n"
        if total_cgst > 0 or total_sgst > 0:
            res += f"Total CGST: ₹{round(total_cgst, 2)}\n"
            res += f"Total SGST: ₹{round(total_sgst, 2)}\n"
        res += f"Grand Total: ₹{round(grand_total, 2)}"
        
        return res

def cancel_bill(chat_id: int) -> str:
    """Cancel the current draft bill."""
    with get_db_cursor() as cursor:
        cursor.execute("UPDATE bills SET status = 'cancelled' WHERE chat_id = ? AND status = 'draft'", (chat_id,))
        if cursor.rowcount > 0:
            return "✅ Draft bill cancelled."
        return "❌ No active draft bill to cancel."

def finalize_bill(chat_id: int, payment_mode: str, khata_customer: str = None, txn_id: str = None) -> str:
    """
    Finalize the draft bill, decrement stock, and apply to khata if applicable.
    payment_mode must be 'cash', 'upi', 'card', or 'khata'.
    """
    if not txn_id:
        txn_id = str(uuid.uuid4())
    
    if payment_mode.lower() not in ['cash', 'upi', 'card', 'khata']:
        return "❌ Error: payment_mode must be 'cash', 'upi', 'card', or 'khata'."
        
    if payment_mode.lower() == 'khata' and not khata_customer:
        return "❌ Error: Khata payment mode requires a khata_customer name."
        
    with db_lock:
        with get_db_cursor() as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            
            # 1. Get draft bill
            cursor.execute("SELECT id FROM bills WHERE chat_id = ? AND status = 'draft'", (chat_id,))
            bill_row = cursor.fetchone()
            if not bill_row:
                return "❌ Error: No active draft bill."
            bill_id = bill_row['id']
            
            # 2. Check Khata validity before processing
            if payment_mode.lower() == 'khata':
                cursor.execute("SELECT id FROM khata WHERE chat_id = ? AND customer = ?", (chat_id, khata_customer))
                khata_row = cursor.fetchone()
                if not khata_row:
                    return f"❌ Error: Khata customer '{khata_customer}' not found. Create khata first."
                khata_id = khata_row['id']
            
            # 3. Get bill items and re-verify stock (Concurrency guard)
            cursor.execute("SELECT product_id, quantity, line_total, cgst, sgst FROM bill_items WHERE bill_id = ?", (bill_id,))
            items = cursor.fetchall()
            
            if not items:
                return "❌ Error: Cannot finalize empty bill."
                
            # Idempotency check: Has this txn_id already been used?
            try:
                cursor.execute("SAVEPOINT check_txn")
                cursor.execute("SELECT id FROM bills WHERE txn_id = ?", (txn_id,))
                if cursor.fetchone():
                    return "✅ Bill already finalized (idempotent retry)."
            except Exception:
                cursor.execute("ROLLBACK TO check_txn")
                
            grand_total = sum(item['line_total'] for item in items)
            total_cgst = sum(item['cgst'] for item in items)
            total_sgst = sum(item['sgst'] for item in items)
            subtotal = grand_total - total_cgst - total_sgst
            
            for item in items:
                cursor.execute("SELECT name, stock_qty, cost_price, mrp FROM products WHERE id = ?", (item['product_id'],))
                prod = cursor.fetchone()
                if prod['stock_qty'] < item['quantity']:
                    # Trigger rollback via exception
                    raise ValueError(f"Oversell: '{prod['name']}' has only {prod['stock_qty']} in stock, bill needs {item['quantity']}.")
                if prod['mrp'] < prod['cost_price']:
                    raise ValueError(f"Guardrail: Cannot sell '{prod['name']}' — MRP (₹{prod['mrp']}) is below cost price (₹{prod['cost_price']}).")
            
            # 4. Atomic Stock Decrement
            for item in items:
                cursor.execute(
                    """
                    UPDATE products 
                    SET stock_qty = stock_qty - ? 
                    WHERE id = ? AND stock_qty >= ?
                    """,
                    (item['quantity'], item['product_id'], item['quantity'])
                )
                if cursor.rowcount == 0:
                    raise ValueError("Failed to decrement stock (concurrency issue).")
                    
            # 5. Update Bill Status
            now = datetime.now().isoformat()
            cursor.execute(
                """
                UPDATE bills 
                SET status = 'finalized', payment_mode = ?, khata_customer = ?, 
                    subtotal = ?, total_cgst = ?, total_sgst = ?, grand_total = ?, 
                    txn_id = ?, finalized_at = ?
                WHERE id = ?
                """,
                (payment_mode.lower(), khata_customer, subtotal, total_cgst, total_sgst, grand_total, txn_id, now, bill_id)
            )
            
            # 6. Apply to Khata if needed
            if payment_mode.lower() == 'khata':
                cursor.execute("UPDATE khata SET balance = balance + ? WHERE id = ?", (grand_total, khata_id))
                cursor.execute(
                    "INSERT INTO khata_txns (khata_id, bill_id, amount, note) VALUES (?, ?, ?, ?)",
                    (khata_id, bill_id, grand_total, f"Bill #{bill_id}")
                )
                return f"✅ Bill finalized successfully (ID: {bill_id}). Total: ₹{grand_total}. Added to {khata_customer}'s khata."
                
            return f"✅ Bill finalized successfully (ID: {bill_id}). Total: ₹{grand_total} via {payment_mode}."
