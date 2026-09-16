import os
import sqlite3
from database.connection import get_connection

SEED_PRODUCTS = [
    ("Aashirvaad Atta 5kg", "AASH-ATTA-5KG", "1101", "packet", False, 210, 255, 5.0, 50, 10),
    ("Tata Salt 1kg", "TATA-SALT-1KG", "2501", "packet", False, 20, 28, 5.0, 100, 20),
    ("Amul Butter 100g", "AMUL-BUTTER-100G", "0405", "packet", False, 50, 62, 12.0, 40, 10),
    ("Fortune Sunflower Oil 1L", "FORT-OIL-1L", "1512", "litre", False, 130, 160, 5.0, 30, 5),
    ("Maggi Noodles 70g", "MAGGI-70G", "1902", "packet", False, 12, 14, 18.0, 200, 50),
    ("Parle-G Biscuit 100g", "PARLE-G-100G", "1905", "packet", False, 8, 10, 18.0, 150, 50),
    ("Surf Excel 1kg", "SURF-EXCEL-1KG", "3402", "packet", False, 170, 210, 18.0, 25, 5),
    ("Sugar (loose)", "SUGAR-LOOSE", "1701", "kg", True, 38, 45, 0.0, 100, 20),
    ("Rice (loose)", "RICE-LOOSE", "1006", "kg", True, 42, 55, 0.0, 80, 20),
    ("Dal Toor (loose)", "DAL-TOOR-LOOSE", "0713", "kg", True, 110, 140, 0.0, 50, 10),
    ("Amul Milk 500ml", "AMUL-MILK-500ML", "0401", "packet", False, 25, 30, 5.0, 60, 15),
    ("Cadbury Dairy Milk 50g", "CADBURY-DM-50G", "1806", "packet", False, 35, 50, 18.0, 80, 20)
]

def seed_db(chat_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if already seeded for this chat_id
        cursor.execute("SELECT COUNT(*) FROM products WHERE chat_id = ?", (chat_id,))
        if cursor.fetchone()[0] > 0:
            print(f"Database already contains products for chat_id {chat_id}. Skipping seed.")
            return

        # Prepare products with chat_id prepended
        products_to_insert = [
            (chat_id,) + product for product in SEED_PRODUCTS
        ]

        cursor.executemany(
            """
            INSERT INTO products (
                chat_id, name, sku, hsn_code, unit, is_loose, 
                cost_price, mrp, gst_rate, stock_qty, reorder_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            products_to_insert
        )
        conn.commit()
        print(f"Successfully seeded {len(SEED_PRODUCTS)} products for chat_id {chat_id}.")
    except Exception as e:
        conn.rollback()
        print(f"Error seeding database for chat_id {chat_id}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Test seed with dummy chat_id
    seed_db(123456789)
