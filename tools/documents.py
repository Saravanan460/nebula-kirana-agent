import os
from datetime import datetime
from reportlab.pdfgen import canvas
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import CategoryChartData
from database.connection import get_db_cursor
from tools.preferences import get_preferences

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
if not os.path.exists(ARTIFACTS_DIR):
    os.makedirs(ARTIFACTS_DIR)

def generate_invoice_pdf(chat_id: int, bill_id: int) -> str:
    """Generate a GST-compliant PDF invoice for a finalized bill."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT status, subtotal, total_cgst, total_sgst, grand_total, payment_mode, finalized_at, khata_customer
            FROM bills WHERE id = ? AND chat_id = ?
            """, (bill_id, chat_id)
        )
        bill = cursor.fetchone()
        if not bill:
            return f"❌ Error: Bill {bill_id} not found."
        if bill['status'] != 'finalized':
            return f"❌ Error: Bill {bill_id} is not finalized yet."

        cursor.execute(
            """
            SELECT p.name, p.hsn_code, p.gst_rate, b.quantity, p.unit, b.unit_price, b.cgst, b.sgst, b.line_total
            FROM bill_items b
            JOIN products p ON b.product_id = p.id
            WHERE b.bill_id = ?
            """, (bill_id,)
        )
        items = cursor.fetchall()
        
    prefs = get_preferences(chat_id)
    shop_name = prefs.get('shop_name', 'Nebula Kirana Store')
    gstin = prefs.get('gstin', '29ABCDE1234F1Z5')

    pdf_path = os.path.join(ARTIFACTS_DIR, f"Invoice_{bill_id}.pdf")
    c = canvas.Canvas(pdf_path)
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, shop_name)
    c.setFont("Helvetica", 10)
    c.drawString(50, 785, f"GSTIN: {gstin}")
    date_obj = datetime.fromisoformat(bill['finalized_at'])
    formatted_date = date_obj.strftime("%Y-%m-%d %I:%M %p")
    c.drawString(50, 770, f"Date: {formatted_date}")
    c.drawString(400, 800, f"TAX INVOICE #{bill_id}")
    
    if bill['payment_mode'] == 'khata':
        c.drawString(400, 785, f"Customer: {bill['khata_customer']} (Khata)")
    else:
        c.drawString(400, 785, f"Payment: {bill['payment_mode'].upper()}")

    # Table Header
    y = 730
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Item")
    c.drawString(200, y, "HSN")
    c.drawString(250, y, "Qty")
    c.drawString(300, y, "Price")
    c.drawString(350, y, "GST%")
    c.drawString(400, y, "CGST+SGST")
    c.drawString(480, y, "Total")
    
    c.line(50, y - 5, 550, y - 5)
    
    # Items
    y -= 20
    c.setFont("Helvetica", 10)
    for item in items:
        c.drawString(50, y, item['name'][:25])
        c.drawString(200, y, str(item['hsn_code']))
        c.drawString(250, y, f"{item['quantity']} {item['unit']}")
        c.drawString(300, y, str(item['unit_price']))
        c.drawString(350, y, str(item['gst_rate']))
        c.drawString(400, y, f"{item['cgst']}+{item['sgst']}")
        c.drawString(480, y, str(item['line_total']))
        y -= 20
        if y < 100:
            c.showPage()
            y = 800
            
    c.line(50, y, 550, y)
    y -= 20
    
    # Totals
    c.setFont("Helvetica-Bold", 10)
    c.drawString(350, y, "Subtotal:")
    c.drawString(480, y, f"Rs. {bill['subtotal']}")
    y -= 15
    c.drawString(350, y, "CGST:")
    c.drawString(480, y, f"Rs. {bill['total_cgst']}")
    y -= 15
    c.drawString(350, y, "SGST:")
    c.drawString(480, y, f"Rs. {bill['total_sgst']}")
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Grand Total:")
    c.drawString(480, y, f"Rs. {bill['grand_total']}")
    
    c.save()
    return f"📄 Invoice PDF generated at {pdf_path}. [FILE_READY:{pdf_path}]"

def generate_analysis_pptx(chat_id: int) -> str:
    """Generate a weekly sales analysis PPTX deck."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT p.name, SUM(b.quantity) as qty, SUM(b.line_total) as rev
            FROM bill_items b
            JOIN bills bl ON b.bill_id = bl.id
            JOIN products p ON b.product_id = p.id
            WHERE bl.chat_id = ? AND bl.status = 'finalized'
            GROUP BY p.id
            ORDER BY rev DESC
            LIMIT 5
            """, (chat_id,)
        )
        top_items = cursor.fetchall()
        
        cursor.execute(
            """
            SELECT payment_mode, SUM(grand_total) as total
            FROM bills
            WHERE chat_id = ? AND status = 'finalized'
            GROUP BY payment_mode
            """, (chat_id,)
        )
        payments = cursor.fetchall()

    if not top_items:
        return "❌ Error: Not enough data to generate analysis."

    prs = Presentation()
    
    # Title Slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "Kirana Store - Weekly Analysis"
    subtitle.text = f"Generated on {datetime.now().strftime('%Y-%m-%d')}"
    
    # Chart Slide 1: Top Items by Revenue
    chart_layout = prs.slide_layouts[5]
    slide = prs.slides.add_slide(chart_layout)
    slide.shapes.title.text = "Top Products by Revenue"
    
    chart_data = CategoryChartData()
    chart_data.categories = [item['name'] for item in top_items]
    chart_data.add_series('Revenue (Rs)', [item['rev'] for item in top_items])
    
    x, y, cx, cy = Inches(1), Inches(2), Inches(8), Inches(4.5)
    slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, chart_data
    )
    
    # Chart Slide 2: Payment Modes
    slide2 = prs.slides.add_slide(chart_layout)
    slide2.shapes.title.text = "Revenue by Payment Mode"
    
    pie_data = CategoryChartData()
    pie_data.categories = [p['payment_mode'].upper() for p in payments]
    pie_data.add_series('Revenue', [p['total'] for p in payments])
    
    slide2.shapes.add_chart(
        XL_CHART_TYPE.PIE, x, y, cx, cy, pie_data
    )
    
    pptx_path = os.path.join(ARTIFACTS_DIR, f"Analysis_{chat_id}_{int(datetime.now().timestamp())}.pptx")
    prs.save(pptx_path)
    return f"📊 Analysis PPTX generated at {pptx_path}. [FILE_READY:{pptx_path}]"
