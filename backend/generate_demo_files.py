import csv
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import subprocess

DEMO_DIR = "demo_files"
os.makedirs(DEMO_DIR, exist_ok=True)

# 1. Create CSV
def create_csv():
    filepath = os.path.join(DEMO_DIR, "demo_invoice.csv")
    with open(filepath, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["InvoiceNo", "Date", "Dealer", "Currency", "SubTotal", "Tax", "Total", "Item", "Desc", "Qty", "Price"])
        writer.writerow(["CSV-9901", "2026-10-15", "DAIMLER-DEMO", "USD", "1500.00", "150.00", "1650.00", "PT-100", "Brake Pad Set", "4", "250.00"])
        writer.writerow(["CSV-9901", "2026-10-15", "DAIMLER-DEMO", "USD", "", "", "", "PT-101", "Rotor Assembly", "2", "250.00"])
    print(f"Created: {filepath}")

# 2. Create XML
def create_xml():
    filepath = os.path.join(DEMO_DIR, "demo_invoice.xml")
    root = ET.Element("InvoiceDocument")
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "InvoiceNumber").text = "XML-8802"
    ET.SubElement(header, "Date").text = "2026-10-16"
    ET.SubElement(header, "OEM_ID").text = "DAIMLER-DEMO"
    
    totals = ET.SubElement(header, "Totals")
    ET.SubElement(totals, "Currency").text = "EUR"
    ET.SubElement(totals, "Net").text = "400.00"
    ET.SubElement(totals, "VAT").text = "80.00"
    ET.SubElement(totals, "Gross").text = "480.00"
    
    lines = ET.SubElement(root, "LineItems")
    item1 = ET.SubElement(lines, "Item")
    ET.SubElement(item1, "Code").text = "FL-22"
    ET.SubElement(item1, "Description").text = "Oil Filter"
    ET.SubElement(item1, "Quantity").text = "10"
    ET.SubElement(item1, "UnitPrice").text = "40.00"
    
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
    with open(filepath, "w") as f:
        f.write(xmlstr)
    print(f"Created: {filepath}")

# 3. Create PDF
def create_pdf():
    filepath = os.path.join(DEMO_DIR, "demo_invoice.pdf")
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, 750, "INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, 700, "Invoice Number: PDF-7703")
    c.drawString(50, 680, "Date: 2026-10-17")
    c.drawString(50, 660, "Billed To: DAIMLER-DEMO")
    
    # Draw table header
    c.line(50, 620, 550, 620)
    c.drawString(50, 605, "Item Code")
    c.drawString(150, 605, "Description")
    c.drawString(350, 605, "Qty")
    c.drawString(400, 605, "Unit Price")
    c.drawString(480, 605, "Total")
    c.line(50, 595, 550, 595)
    
    # Draw items
    c.drawString(50, 575, "CH-909")
    c.drawString(150, 575, "Chassis Frame Assembly")
    c.drawString(350, 575, "1")
    c.drawString(400, 575, "$3,500.00")
    c.drawString(480, 575, "$3,500.00")
    
    c.drawString(50, 555, "WH-88")
    c.drawString(150, 555, "Heavy Duty Wheel")
    c.drawString(350, 555, "6")
    c.drawString(400, 555, "$400.00")
    c.drawString(480, 555, "$2,400.00")
    
    c.line(50, 540, 550, 540)
    
    # Totals
    c.drawString(380, 510, "Subtotal:")
    c.drawString(480, 510, "$5,900.00")
    c.drawString(380, 490, "Tax (10%):")
    c.drawString(480, 490, "$590.00")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(380, 460, "Total:")
    c.drawString(480, 460, "$6,490.00")
    
    c.save()
    print(f"Created: {filepath}")

# 4. Create XLSX
def create_xlsx():
    filepath = os.path.join(DEMO_DIR, "demo_invoice.xlsx")
    try:
        import openpyxl
    except ImportError:
        print("Installing openpyxl for XLSX generation...")
        subprocess.check_call(["pip", "install", "openpyxl"])
        import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoice Data"
    
    headers = ["InvoiceNum", "InvDate", "DealerCode", "Item SKU", "Item Desc", "Quantity", "Price", "Row Total", "Invoice Total"]
    ws.append(headers)
    ws.append(["XLSX-6604", "10/18/2026", "DAIMLER-DEMO", "EN-101", "V8 Engine Block", 1, 8000.00, 8000.00, 8800.00])
    ws.append(["XLSX-6604", "10/18/2026", "DAIMLER-DEMO", "EX-202", "Exhaust System", 1, 800.00, 800.00, ""])
    
    wb.save(filepath)
    print(f"Created: {filepath}")

if __name__ == "__main__":
    create_csv()
    create_xml()
    create_pdf()
    create_xlsx()
    print("\nAll demo files created in the 'demo_files' directory.")
