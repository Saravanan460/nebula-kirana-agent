from database.connection import get_db_cursor, db_lock

def add_product(name: str, sku: str, hsn_code: str, unit: str, is_loose: bool, cost_price: float, mrp: float, gst_rate: float, reorder_level: float = 10.0) -> str:
    """
    Add a new product (SKU) to the inventory.
    Args:
        name: Name of the product (e.g. "Aashirvaad Atta 5kg")
        sku: Unique SKU code
        hsn_code: GST HSN code
        unit: Unit of measurement (kg, g, litre, ml, packet, dozen, piece)
        is_loose: True if sold by weight/loose, False if packaged
        cost_price: Cost price in INR
        mrp: Maximum Retail Price (Sell Price) in INR
        gst_rate: GST rate percentage (0, 5, 12, 18)
        reorder_level: Stock level at which to reorder
    """
    if gst_rate not in [0.0, 5.0, 12.0, 18.0, 28.0]:
        return "❌ Error: Invalid GST rate. Must be 0, 5, 12, 18, or 28."
    if mrp < cost_price:
        return "❌ Error: Guardrail blocked - MRP cannot be less than cost_price."
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO products (name, sku, hsn_code, unit, is_loose, cost_price, mrp, gst_rate, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, sku, hsn_code, unit, is_loose, cost_price, mrp, gst_rate, reorder_level)
            )
            return f"✅ Product '{name}' added successfully with SKU '{sku}'."
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            return f"❌ Error: Product with SKU '{sku}' already exists."
        return f"❌ Error adding product: {str(e)}"

def receive_stock(sku: str, quantity: float, new_cost_price: float = None, new_mrp: float = None) -> str:
    """
    Receive new stock for an existing product. 
    Args:
        sku: SKU of the product
        quantity: Quantity received
        new_cost_price: Optional updated cost price
        new_mrp: Optional updated MRP
    """
    if quantity <= 0:
        return "❌ Error: Quantity must be positive."
        
    with db_lock:
        with get_db_cursor() as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            
            cursor.execute("SELECT id, name, cost_price, mrp FROM products WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            if not row:
                return f"❌ Error: Product with SKU '{sku}' not found."
            
            cost = new_cost_price if new_cost_price is not None else row['cost_price']
            mrp = new_mrp if new_mrp is not None else row['mrp']
            
            if mrp < cost:
                return "❌ Error: Guardrail blocked - MRP cannot be less than cost_price."
            
            cursor.execute(
                """
                UPDATE products 
                SET stock_qty = stock_qty + ?, cost_price = ?, mrp = ?
                WHERE sku = ?
                """,
                (quantity, cost, mrp, sku)
            )
            
            cursor.execute("SELECT stock_qty FROM products WHERE sku = ?", (sku,))
            new_stock = cursor.fetchone()['stock_qty']
            
            return f"✅ Received {quantity} units of '{row['name']}'. New stock: {new_stock}."

def check_stock(sku: str = None) -> str:
    """
    Check stock for a specific SKU. If sku is None, DO NOT USE to get all stock. Use search_product instead for finding items.
    """
    if sku is None:
        return "❌ Error: Please provide an SKU. Use search_product to find SKUs."
        
    with get_db_cursor() as cursor:
        cursor.execute("SELECT name, stock_qty, unit, mrp FROM products WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        if not row:
            return f"❌ Error: Product with SKU '{sku}' not found."
        
        return f"📦 {row['name']} - Stock: {row['stock_qty']} {row['unit']} (MRP: ₹{row['mrp']})"

def low_stock_report() -> str:
    """
    Get a list of all products that are at or below their reorder level.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT name, sku, stock_qty, reorder_level 
            FROM products 
            WHERE stock_qty <= reorder_level AND is_active = 1
            ORDER BY (stock_qty - reorder_level) ASC
            """
        )
        rows = cursor.fetchall()
        
        if not rows:
            return "✅ All product stocks are above reorder levels."
            
        report = "⚠️ Low Stock Report:\n"
        for r in rows:
            report += f"- {r['name']} (SKU: {r['sku']}) - Stock: {r['stock_qty']} (Reorder at: {r['reorder_level']})\n"
        return report

def search_product(query: str) -> str:
    """
    Fuzzy search for products by name to find their SKUs and details.
    Use this when the user mentions a product name to get the exact SKU for billing.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT name, sku, stock_qty, mrp, unit 
            FROM products 
            WHERE name LIKE ? AND is_active = 1
            LIMIT 10
            """,
            (f"%{query}%",)
        )
        rows = cursor.fetchall()
        
        if not rows:
            return f"❌ No products found matching '{query}'."
            
        results = [f"Found {len(rows)} products matching '{query}':"]
        for r in rows:
            results.append(f"- {r['name']} | SKU: {r['sku']} | ₹{r['mrp']} | Stock: {r['stock_qty']} {r['unit']}")
        return "\n".join(results)
