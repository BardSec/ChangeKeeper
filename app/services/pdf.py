from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from io import BytesIO
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape as xml_escape
import json


class PDFGenerator:
    """Generate PDF reports for change records."""

    @staticmethod
    def _esc(value) -> str:
        """Escape user content for safe ReportLab Paragraph rendering."""
        if value is None:
            return ''
        return xml_escape(str(value))

    @staticmethod
    def generate_change_pdf(change: dict) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72
        )

        elements = []
        styles = getSampleStyleSheet()
        esc = PDFGenerator._esc

        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            fontSize=16, textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12, alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'],
            fontSize=12, textColor=colors.HexColor('#333333'),
            spaceAfter=6, spaceBefore=12
        )
        normal_style = styles['Normal']

        elements.append(Paragraph("IT Change Record", title_style))
        elements.append(Spacer(1, 0.2*inch))

        header_data = [
            ['Change ID:', str(change['id'])],
            ['Created:', PDFGenerator._format_datetime(change['created_at'])],
            ['Created By:', esc(change['created_by'])],
            ['Status:', esc(change['status'])],
        ]

        header_table = Table(header_data, colWidths=[2*inch, 4.5*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.3*inch))

        # Section 1: Basics
        elements.append(Paragraph("Change Details", heading_style))

        basics_data = [
            ['Title:', esc(change['title'])],
            ['Category:', esc(change['category'])],
            ['Systems Affected:', esc(', '.join(json.loads(change['systems_affected'])))],
            ['Implementer:', esc(change['implementer'])],
        ]

        if change.get('planned_start'):
            basics_data.append(['Planned Start:', PDFGenerator._format_datetime(change['planned_start'])])
        if change.get('planned_end'):
            basics_data.append(['Planned End:', PDFGenerator._format_datetime(change['planned_end'])])

        basics_table = Table(basics_data, colWidths=[2*inch, 4.5*inch])
        basics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(basics_table)
        elements.append(Spacer(1, 0.2*inch))

        # Section 2: Risk Assessment
        elements.append(Paragraph("Risk Assessment", heading_style))

        risk_data = [
            ['Impact Level:', esc(change['impact_level'])],
            ['User Impact:', esc(change['user_impact'])],
            ['Maintenance Window:', 'Yes' if change['maintenance_window'] else 'No'],
        ]

        risk_table = Table(risk_data, colWidths=[2*inch, 4.5*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(risk_table)

        if change.get('backout_plan'):
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("<b>Backout Plan:</b>", normal_style))
            elements.append(Paragraph(esc(change['backout_plan']), normal_style))

        elements.append(Spacer(1, 0.2*inch))

        # Section 3: Work Details
        elements.append(Paragraph("Work Details", heading_style))
        elements.append(Paragraph("<b>What Changed:</b>", normal_style))
        elements.append(Paragraph(esc(change['what_changed']), normal_style))
        elements.append(Spacer(1, 0.1*inch))

        if change.get('ticket_id'):
            elements.append(Paragraph(f"<b>Ticket/Issue ID:</b> {esc(change['ticket_id'])}", normal_style))
            elements.append(Spacer(1, 0.1*inch))

        if change.get('links'):
            links = json.loads(change['links'])
            if links:
                elements.append(Paragraph("<b>Related Links:</b>", normal_style))
                for link in links:
                    elements.append(Paragraph(f"\u2022 {esc(link)}", normal_style))
                elements.append(Spacer(1, 0.1*inch))

        # Section 4: Completion
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("Completion", heading_style))

        if change.get('outcome_notes'):
            elements.append(Paragraph("<b>Outcome Notes:</b>", normal_style))
            elements.append(Paragraph(esc(change['outcome_notes']), normal_style))
            elements.append(Spacer(1, 0.1*inch))

        if change.get('post_change_issues'):
            elements.append(Paragraph("<b>Post-Change Issues:</b>", normal_style))
            elements.append(Paragraph(esc(change['post_change_issues']), normal_style))

        # Footer
        elements.append(Spacer(1, 0.3*inch))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(footer_text, ParagraphStyle(
            'Footer', parent=styles['Normal'],
            fontSize=8, textColor=colors.grey, alignment=TA_CENTER
        )))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _format_datetime(dt) -> str:
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return dt

        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

        return str(dt)
