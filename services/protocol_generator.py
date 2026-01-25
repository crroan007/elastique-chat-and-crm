import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

class ProtocolGenerator:
    """
    Generates a branded 'Lymphatic Wellness Protocol' PDF.
    Separates recommendations into Daily and Weekly commitments.
    """
    
    def __init__(self, output_dir="static/protocols"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_pdf(self, conversation_id, user_name, root_cause, daily_items, weekly_items, email=None):
        filename = f"Elastique_Protocol_{conversation_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor("#2C3E50"),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor("#34495E"),
            spaceBefore=20,
            spaceAfter=10
        )
        
        normal_style = styles['Normal']
        normal_style.fontSize = 12
        normal_style.leading = 16
        
        story = []
        
        # 1. Branding / Title
        # TODO: Add Logo Image here using Image('path/to/logo.png')
        story.append(Paragraph("Elastique", title_style))
        story.append(Paragraph("Your Personalized Lymphatic Wellness Protocol", ParagraphStyle('Sub', parent=normal_style, alignment=TA_CENTER, fontSize=14)))
        story.append(Spacer(1, 30))
        
        # 2. User Info
        date_str = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"Prepared for: <b>{user_name}</b>", normal_style))
        story.append(Paragraph(f"Date: {date_str}", normal_style))
        if email:
             story.append(Paragraph(f"Email: {email}", normal_style))
        story.append(Spacer(1, 20))
        
        # 3. Root Cause Analysis
        story.append(Paragraph("Analysis & Focus", header_style))
        story.append(Paragraph(f"Based on our consultation, your primary focus is: <b>{root_cause}</b>.", normal_style))
        story.append(Paragraph("This protocol is designed to support your lymphatic system through specific movement, compression, and lifestyle adjustments.", normal_style))
        story.append(Spacer(1, 20))
        
        # 4. Daily Protocol Table
        story.append(Paragraph("Your Daily Commitments", header_style))
        
        daily_data = [["Action", "Duration / Frequency"]]
        for item in daily_items:
            # item assumed to be dict {action: "Legs Up Wall", details: "10 mins"}
            daily_data.append([item.get('action'), item.get('details')])
            
        t_daily = Table(daily_data, colWidths=[300, 150])
        t_daily.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7"))
        ]))
        story.append(t_daily)
        story.append(Spacer(1, 20))
        
        # 5. Weekly Protocol Table
        if weekly_items:
            story.append(Paragraph("Your Weekly Goals", header_style))
            weekly_data = [["Activity", "Target"]]
            for item in weekly_items:
                weekly_data.append([item.get('action'), item.get('details')])
                
            t_weekly = Table(weekly_data, colWidths=[300, 150])
            t_weekly.setStyle(TableStyle([
               ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
               ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
               ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7"))
            ]))
            story.append(t_weekly)
            story.append(Spacer(1, 30))
        
        # 6. Disclaimer
        disclaimer_text = ("<b>Disclaimer:</b> This document contains wellness recommendations for supporting lymphatic health. "
                           "It is not medical advice, diagnosis, or treatment. "
                           "Please consult with your physician before beginning any new exercise or compression regimen.")
        
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=normal_style,
            fontSize=10,
            textColor=colors.gray,
            alignment=TA_CENTER
        )
        story.append(Paragraph(disclaimer_text, disclaimer_style))
        
        # Build
        doc.build(story)
        
        return filepath

# Test Logic
if __name__ == "__main__":
    gen = ProtocolGenerator()
    path = gen.generate_pdf(
        "test_123", 
        "Jane Doe", 
        "Venous Insufficiency / Travel Swelling",
        [{"action": "Legs Up The Wall", "details": "10 Minutes (Evening)"}, {"action": "Wear Compression", "details": "During Flights (>3hrs)"}],
        [{"action": "Zone 2 Cardio", "details": "3x per week (30 mins)"}]
    )
    print(f"Generated: {path}")
