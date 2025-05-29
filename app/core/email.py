import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

from app.core.config import settings


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME

        # Initialize Jinja2 for email templates
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email to recipients"""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = ", ".join(to_emails)

            # Add text part
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)

            # Add HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)

            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    async def send_welcome_email(self, email: str, name: str) -> bool:
        """Send welcome email to new user"""
        subject = f"Welcome to {settings.APP_NAME}!"
        
        # For now, use simple HTML without template
        html_content = f"""
        <html>
            <body>
                <h2>Welcome to {settings.APP_NAME}, {name}!</h2>
                <p>Thank you for registering. We're excited to have you on board.</p>
                <p>Get started by exploring our features and uploading your first file.</p>
                <br>
                <p>Best regards,<br>The {settings.APP_NAME} Team</p>
            </body>
        </html>
        """
        
        text_content = f"""
        Welcome to {settings.APP_NAME}, {name}!
        
        Thank you for registering. We're excited to have you on board.
        
        Get started by exploring our features and uploading your first file.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        return await self.send_email([email], subject, html_content, text_content)

    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Send password reset email"""
        subject = f"Reset your {settings.APP_NAME} password"
        reset_url = f"{settings.GOOGLE_REDIRECT_URI.replace('/api/v1/auth/google/callback', '')}/reset-password?token={reset_token}"
        
        html_content = f"""
        <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>You have requested to reset your password. Click the link below to create a new password:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <br>
                <p>Best regards,<br>The {settings.APP_NAME} Team</p>
            </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        You have requested to reset your password. Visit the link below to create a new password:
        
        {reset_url}
        
        This link will expire in 24 hours.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        return await self.send_email([email], subject, html_content, text_content)


# Global email service instance
email_service = EmailService()


async def get_email_service() -> EmailService:
    """Dependency to get email service"""
    return email_service 