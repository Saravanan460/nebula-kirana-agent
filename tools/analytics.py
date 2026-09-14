from datetime import datetime, date
from database.connection import get_db_cursor
import json

def daily_summary(chat_id: int, target_date: str = None) -> str:
    """Get the summary of today's sales (or a specific date YYYY-MM-DD)."""
    if not target_date:
        target_date = date.today().isoformat()
        
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(id) as bills_count, SUM(subtotal) as subtotal, 
                   SUM(total_cgst) as cgst, SUM(total_sgst) as sgst, 
                   SUM(grand_total) as grand_total
            FROM bills
            WHERE chat_id = ? AND status = 'finalized' AND date(finalized_at) = ?
            """, (chat_id, target_date)
        )
        totals = cursor.fetchone()
        
        if not totals or not totals['bills_count']:
            return f"📉 No finalized bills found for {target_date}."
            
        cursor.execute(
            """
            SELECT payment_mode, SUM(grand_total) as amount
            FROM bills
            WHERE chat_id = ? AND status = 'finalized' AND date(finalized_at) = ?
            GROUP BY payment_mode
            """, (chat_id, target_date)
        )
        payments = cursor.fetchall()
        
        res = f"📊 Daily Summary ({target_date})\n"
        res += f"Total Bills: {totals['bills_count']}\n"
        res += f"Total Sales: ₹{totals['grand_total'] or 0}\n"
        res += f"Tax Collected: CGST ₹{totals['cgst'] or 0} | SGST ₹{totals['sgst'] or 0}\n\n"
        
        res += "Payment Breakdown:\n"
        for p in payments:
            res += f"- {p['payment_mode'].upper()}: ₹{p['amount']}\n"
            
        return res

def close_day(chat_id: int) -> str:
    """Snapshot today's sales into the daily_close table."""
    today = date.today().isoformat()
    
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(id) as bills_count, SUM(total_cgst) as cgst, 
                   SUM(total_sgst) as sgst, SUM(grand_total) as grand_total
            FROM bills
            WHERE chat_id = ? AND status = 'finalized' AND date(finalized_at) = ?
            """, (chat_id, today)
        )
        totals = cursor.fetchone()
        
        if not totals or not totals['bills_count']:
            return "❌ Error: Cannot close day with zero sales."
            
        cursor.execute(
            """
            SELECT payment_mode, SUM(grand_total) as amount
            FROM bills
            WHERE chat_id = ? AND status = 'finalized' AND date(finalized_at) = ?
            GROUP BY payment_mode
            """, (chat_id, today)
        )
        payments = cursor.fetchall()
        
        cash_total = sum(p['amount'] for p in payments if p['payment_mode'] == 'cash')
        upi_total = sum(p['amount'] for p in payments if p['payment_mode'] == 'upi')
        card_total = sum(p['amount'] for p in payments if p['payment_mode'] == 'card')
        khata_total = sum(p['amount'] for p in payments if p['payment_mode'] == 'khata')
        
        # Get top items
        cursor.execute(
            """
            SELECT p.name, SUM(b.quantity) as qty
            FROM bill_items b
            JOIN bills bl ON b.bill_id = bl.id
            JOIN products p ON p.id = b.product_id
            WHERE bl.chat_id = ? AND bl.status = 'finalized' AND date(bl.finalized_at) = ?
            GROUP BY p.id
            ORDER BY qty DESC
            LIMIT 5
            """, (chat_id, today)
        )
        top_items = [{"name": row['name'], "qty": row['qty']} for row in cursor.fetchall()]
        
        try:
            cursor.execute(
                """
                INSERT INTO daily_close (
                    chat_id, close_date, total_sales, total_cgst, total_sgst, 
                    cash_total, upi_total, card_total, bills_count, top_items
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, today, totals['grand_total'], totals['cgst'], totals['sgst'], 
                 cash_total, upi_total, card_total, totals['bills_count'], json.dumps(top_items))
            )
            return f"✅ Day closed successfully for {today}. Total Sales: ₹{totals['grand_total']}."
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return f"❌ Error: Day {today} is already closed."
            return f"❌ Error closing day: {e}"
