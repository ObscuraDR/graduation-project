import io
import logging
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)

def generate_security_report_pdf(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    Tạo một báo cáo bảo mật dưới dạng file PDF từ dữ liệu báo cáo.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    h1_style = styles['h1']
    h1_style.alignment = 1 # Center
    h1_style.spaceAfter = 0.2 * inch

    h2_style = styles['h2']
    h2_style.spaceBefore = 0.2 * inch
    h2_style.spaceAfter = 0.1 * inch

    normal_style = styles['Normal']
    normal_style.spaceAfter = 0.1 * inch

    # Story elements
    story: List[Any] = []

    # Title
    story.append(Paragraph("Z-Sentinel IDS Security Report", h1_style))
    story.append(Paragraph(f"Report ID: {report_data.get('report_id', 'N/A')}", normal_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", normal_style))
    story.append(Spacer(1, 0.2 * inch))

    # Report Period
    period_start = datetime.fromisoformat(report_data['period_start'].replace('Z', '+00:00')) if isinstance(report_data['period_start'], str) else report_data['period_start']
    period_end = datetime.fromisoformat(report_data['period_end'].replace('Z', '+00:00')) if isinstance(report_data['period_end'], str) else report_data['period_end']
    story.append(Paragraph(f"<b>Report Period:</b> {period_start.strftime('%Y-%m-%d %H:%M:%S')} to {period_end.strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    # Summary
    story.append(Paragraph("Summary", h2_style))
    summary_text = report_data.get('summary', 'No summary provided.')
    story.append(Paragraph(summary_text, normal_style))
    story.append(Spacer(1, 0.1 * inch))

    # Alert Statistics
    story.append(Paragraph("Alert Statistics", h2_style))
    alert_stats_data = [
        ['Metric', 'Value'],
        ['Total Alerts', report_data.get('total_alerts', 0)],
        ['Critical Alerts', report_data.get('critical_count', 0)],
        ['High Alerts', report_data.get('high_count', 0)],
        ['Medium Alerts', report_data.get('medium_count', 0)],
        ['Low Alerts', report_data.get('low_count', 0)],
        ['Auto Blocked IPs', report_data.get('auto_blocked_count', 0)],
        ['Geo Blocked Countries', report_data.get('geo_blocked_count', 0)],
    ]
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')), # bg-gray-700
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#2d3748')), # bg-gray-800
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#e2e8f0')), # text-gray-200
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4a5568')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    table = Table(alert_stats_data)
    table.setStyle(table_style)
    story.append(table)
    story.append(Spacer(1, 0.1 * inch))

    # Top Attackers
    top_attackers = report_data.get('top_attackers', [])
    if top_attackers:
        story.append(Paragraph("Top Attackers", h2_style))
        attacker_data = [['IP Address', 'Count', 'Attack Type']]
        for attacker in top_attackers:
            attacker_data.append([
                attacker.get('ip', 'N/A'),
                attacker.get('count', 0),
                attacker.get('attack_type', 'N/A')
            ])
        table = Table(attacker_data)
        table.setStyle(table_style)
        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

    # Top Attack Types
    top_attack_types = report_data.get('top_attack_types', [])
    if top_attack_types:
        story.append(Paragraph("Top Attack Types", h2_style))
        attack_type_data = [['Attack Type', 'Count']]
        for atype in top_attack_types:
            attack_type_data.append([
                atype.get('type', 'N/A'),
                atype.get('count', 0)
            ])
        table = Table(attack_type_data)
        table.setStyle(table_style)
        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer