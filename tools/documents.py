import os
from datetime import datetime
from reportlab.pdfgen import canvas
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import CategoryChartData
from database.connection import get_db_cursor
from tools.preferences import get_preferences
from tools.file_queue import queue_file

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
if not os.path.exists(ARTIFACTS_DIR):
    os.makedirs(ARTIFACTS_DIR)

def generate_invoice_pdf(chat_id: int, bill_id: int) -> str:
    """Generate a GST-compliant PDF invoice for a finalized bill."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT status, subtotal, total_cgst, total_sgst, grand_total, payment_mode, finalized_at, khata_customer, customer_name
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
        cust_name = bill['customer_name'] or "Walk-in"
        c.drawString(400, 785, f"Customer: {cust_name} ({bill['payment_mode'].upper()})")

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
    c.drawString(480, y, f"Rs. {bill['subtotal']:.2f}")
    y -= 15
    c.drawString(350, y, "CGST:")
    c.drawString(480, y, f"Rs. {bill['total_cgst']:.2f}")
    y -= 15
    c.drawString(350, y, "SGST:")
    c.drawString(480, y, f"Rs. {bill['total_sgst']:.2f}")
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Grand Total:")
    c.drawString(480, y, f"Rs. {bill['grand_total']:.2f}")
    
    c.save()
    queue_file(chat_id, pdf_path)
    return f"📄 Invoice PDF for Bill #{bill_id} has been generated and will be sent as a downloadable file."

def generate_analysis_pptx(chat_id: int) -> str:
    """Generate a weekly sales analysis PPTX deck."""
    with get_db_cursor() as cursor:
        # Get overall stats
        cursor.execute(
            """
            SELECT COUNT(id) as bills_count, SUM(subtotal) as subtotal, 
                   SUM(total_cgst) as cgst, SUM(total_sgst) as sgst, 
                   SUM(grand_total) as grand_total
            FROM bills
            WHERE chat_id = ? AND status = 'finalized'
            """, (chat_id,)
        )
        overall = cursor.fetchone()
        
        # Get item stats with profit
        cursor.execute(
            """
            SELECT p.name, SUM(b.quantity) as qty, SUM(b.line_total) as rev,
                   SUM(b.line_total) - SUM(b.quantity * p.cost_price) as profit
            FROM bill_items b
            JOIN bills bl ON b.bill_id = bl.id
            JOIN products p ON b.product_id = p.id
            WHERE bl.chat_id = ? AND bl.status = 'finalized'
            GROUP BY p.id
            ORDER BY rev DESC
            """, (chat_id,)
        )
        top_items = cursor.fetchall()
        
        # Payment modes
        cursor.execute(
            """
            SELECT payment_mode, SUM(grand_total) as total
            FROM bills
            WHERE chat_id = ? AND status = 'finalized'
            GROUP BY payment_mode
            """, (chat_id,)
        )
        payments = cursor.fetchall()

    if not top_items or not overall or not overall['bills_count']:
        return "❌ Error: Not enough data to generate analysis."

    prs = Presentation()
    x, y, cx, cy = Inches(1), Inches(2), Inches(8), Inches(4.5)
    
    # Slide 1: Title Slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "Kirana Store - Weekly Analysis"
    subtitle.text = f"Generated on {datetime.now().strftime('%Y-%m-%d')}"
    
    # Slide 2: Summary KPIs
    bullet_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_layout)
    slide2.shapes.title.text = "Overall Summary"
    body = slide2.shapes.placeholders[1]
    tf = body.text_frame
    
    total_profit = sum(item['profit'] for item in top_items)
    total_items = sum(item['qty'] for item in top_items)
    
    tf.text = f"Total Revenue: Rs. {overall['grand_total']:.2f}"
    p = tf.add_paragraph()
    p.text = f"Total Profit: Rs. {total_profit:.2f}"
    p = tf.add_paragraph()
    p.text = f"Total Bills Generated: {overall['bills_count']}"
    p = tf.add_paragraph()
    p.text = f"Items Sold: {total_items} units"
    p = tf.add_paragraph()
    p.text = f"Tax Collected: Rs. {(overall['cgst'] or 0) + (overall['sgst'] or 0):.2f}"
    
    # Slide 3: Chart - Top Items by Revenue
    chart_layout = prs.slide_layouts[5]
    slide3 = prs.slides.add_slide(chart_layout)
    slide3.shapes.title.text = "Top Products by Revenue"
    
    chart_data = CategoryChartData()
    chart_data.categories = [item['name'][:15] for item in top_items[:7]]
    chart_data.add_series('Revenue (Rs)', [item['rev'] for item in top_items[:7]])
    
    chart_shape = slide3.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, chart_data
    )
    chart = chart_shape.chart
    chart.has_legend = True
    chart.legend.include_in_layout = False
    
    # Slide 4: Chart - Profit Analysis
    slide4 = prs.slides.add_slide(chart_layout)
    slide4.shapes.title.text = "Profit Analysis by Product"
    
    profit_data = CategoryChartData()
    profit_data.categories = [item['name'][:15] for item in top_items[:7]]
    profit_data.add_series('Profit (Rs)', [item['profit'] for item in top_items[:7]])
    
    chart_shape2 = slide4.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, profit_data
    )
    chart2 = chart_shape2.chart
    chart2.has_legend = True
    chart2.legend.include_in_layout = False
    
    # Slide 5: Payment Modes
    slide5 = prs.slides.add_slide(chart_layout)
    slide5.shapes.title.text = "Revenue by Payment Mode"
    
    pie_data = CategoryChartData()
    pie_data.categories = [p['payment_mode'].upper() for p in payments]
    pie_data.add_series('Revenue', [p['total'] for p in payments])
    
    chart_shape3 = slide5.shapes.add_chart(
        XL_CHART_TYPE.PIE, x, y, cx, cy, pie_data
    )
    chart3 = chart_shape3.chart
    chart3.has_legend = True
    chart3.legend.include_in_layout = False
    
    pptx_path = os.path.join(ARTIFACTS_DIR, f"Analysis_{chat_id}_{int(datetime.now().timestamp())}.pptx")
    prs.save(pptx_path)
    queue_file(chat_id, pptx_path)
    return f"📊 Weekly Sales Analysis deck has been generated and will be sent as a downloadable file."
