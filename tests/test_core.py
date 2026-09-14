import os
import threading
import time

# Set env var for testing db before importing anything else
os.environ["TESTING"] = "True"

from database.schema import setup_db
from database.connection import get_connection
from tools.inventory import add_product, receive_stock, check_stock
from tools.billing import start_bill, add_item_to_bill, edit_bill_item, finalize_bill, view_bill
from tools.khata import create_khata

def run_tests():
    # 1. Clean and setup test DB
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    setup_db()
    
    chat_id = 12345
    
    # 2. Test Inventory Guardrails
    print("--- Testing Inventory ---")
    res = add_product("Test Atta", "TEST-ATTA", "1101", "packet", False, 100, 90, 5.0)
    assert "MRP cannot be less than cost_price" in res, "Failed: Allowed selling below cost"
    print("Guardrail: MRP < Cost - Passed")
    
    res = add_product("Test Atta", "TEST-ATTA", "1101", "packet", False, 100, 120, 5.0)
    assert "successfully" in res, "Failed: Valid product addition"
    print("Valid product added - Passed")
    
    res = receive_stock("TEST-ATTA", 10)
    assert "New stock: 10" in res, "Failed: Stock receive"
    print("Stock received - Passed")
    
    # 3. Test Billing & Oversell Guardrail
    print("\n--- Testing Billing ---")
    start_bill(chat_id)
    
    # Oversell check
    res = add_item_to_bill(chat_id, "TEST-ATTA", 15)
    assert "Oversell" in res, "Failed: Allowed adding more than stock"
    print("Guardrail: Oversell in add_item - Passed")
    
    # Valid add
    res = add_item_to_bill(chat_id, "TEST-ATTA", 5)
    assert "Added" in res, "Failed: Valid add"
    print("Valid add_item - Passed")
    
    # GST check in view
    bill_view = view_bill(chat_id)
    assert "CGST ₹15.0" in bill_view and "SGST ₹15.0" in bill_view, f"Failed GST calc: {bill_view}"
    # base = 120 * 5 = 600. 5% GST = 30. CGST 15, SGST 15.
    print("GST calculation correct - Passed")
    
    # Finalize
    res = finalize_bill(chat_id, "cash")
    assert "successfully" in res, "Failed: Finalize bill"
    print("Finalize bill - Passed")
    
    # Check stock after finalize
    res = check_stock("TEST-ATTA")
    assert "Stock: 5" in res, "Failed: Stock didn't decrement correctly"
    print("Stock decremented atomically - Passed")

    # 4. Test Concurrency
    print("\n--- Testing Concurrency ---")
    # Add stock back
    receive_stock("TEST-ATTA", 10) # Total stock now 15
    
    # Start two bills for different chats
    start_bill(111)
    start_bill(222)
    
    add_item_to_bill(111, "TEST-ATTA", 10)
    add_item_to_bill(222, "TEST-ATTA", 10)
    
    def finalize_thread(cid, results_dict):
        try:
            res = finalize_bill(cid, "cash")
            results_dict[cid] = res
        except Exception as e:
            results_dict[cid] = str(e)
            
    results = {}
    t1 = threading.Thread(target=finalize_thread, args=(111, results))
    t2 = threading.Thread(target=finalize_thread, args=(222, results))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    success_count = sum("successfully" in str(v) for v in results.values())
    fail_count = sum("Oversell" in str(v) for v in results.values())
    
    assert success_count == 1 and fail_count == 1, f"Failed concurrency: {results}"
    print("Concurrency guard (one succeeds, one fails due to oversell) - Passed")

    print("\n=== ALL TESTS PASSED ===")
    
if __name__ == "__main__":
    run_tests()
