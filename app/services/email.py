import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape as html_escape
from typing import Optional
from app.config import get_settings
import json

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailService:
    """Email service for sending change notifications (pluggable module)."""

    @staticmethod
    def is_enabled() -> bool:
        """Check if email service is enabled."""
        return settings.enable_email and bool(settings.smtp_host)

    @staticmethod
    def send_change_summary(
        recipient_email: str,
        change: dict,
        change_url: str
    ) -> bool:
        if not EmailService.is_enabled():
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Change Record: {change['title'][:100]}"
            msg['From'] = settings.smtp_from
            msg['To'] = recipient_email

            text_content = EmailService._create_text_summary(change, change_url)
            html_content = EmailService._create_html_summary(change, change_url)

            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            return True

        except Exception:
            logger.exception("Email send failed")
            return False

    @staticmethod
    def _create_text_summary(change: dict, change_url: str) -> str:
        systems = ', '.join(json.loads(change['systems_affected']))

        text = f"""
IT Change Record Summary

Change ID: {change['id']}
Title: {change['title']}
Status: {change['status']}

Category: {change['category']}
Systems Affected: {systems}
Impact Level: {change['impact_level']}
Implementer: {change['implementer']}

View full details: {change_url}

---
This is an automated notification. Sensitive details are not included in this email.
Please use the link above to view the complete change record.
"""
        return text.strip()

    @staticmethod
    def _create_html_summary(change: dict, change_url: str) -> str:
        systems = ', '.join(json.loads(change['systems_affected']))

        # HTML-escape all user-controlled values
        e_title = html_escape(str(change['title']))
        e_status = html_escape(str(change['status']))
        e_category = html_escape(str(change['category']))
        e_systems = html_escape(systems)
        e_impact = html_escape(str(change['impact_level']))
        e_implementer = html_escape(str(change['implementer']))
        e_url = html_escape(change_url)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #0078d4; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; margin-top: 20px; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ margin-left: 10px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #0078d4;
                   color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;
                   font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IT Change Record Summary</h1>
        </div>

        <div class="content">
            <div class="field">
                <span class="label">Change ID:</span>
                <span class="value">{change['id']}</span>
            </div>

            <div class="field">
                <span class="label">Title:</span>
                <span class="value">{e_title}</span>
            </div>

            <div class="field">
                <span class="label">Status:</span>
                <span class="value">{e_status}</span>
            </div>

            <div class="field">
                <span class="label">Category:</span>
                <span class="value">{e_category}</span>
            </div>

            <div class="field">
                <span class="label">Systems Affected:</span>
                <span class="value">{e_systems}</span>
            </div>

            <div class="field">
                <span class="label">Impact Level:</span>
                <span class="value">{e_impact}</span>
            </div>

            <div class="field">
                <span class="label">Implementer:</span>
                <span class="value">{e_implementer}</span>
            </div>

            <a href="{e_url}" class="button">View Full Details</a>
        </div>

        <div class="footer">
            <p>This is an automated notification. Sensitive details are not included in this email.</p>
            <p>Please use the link above to view the complete change record.</p>
        </div>
    </div>
</body>
</html>
"""
        return html.strip()
