import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
_raw_password = os.getenv("SMTP_APP_PASSWORD", "")
SMTP_APP_PASSWORD = _raw_password.replace(" ", "") if _raw_password else ""
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def send_otp_email(to_email: str, otp: str):
    """
    Sends a 6-digit OTP to the user's email address using Gmail SMTP.
    Fallback prints OTP to console if SMTP credentials are missing or server connection fails.
    """
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in SMTP_EMAIL.lower() or "your_" in SMTP_APP_PASSWORD.lower():
        print(f"[OTP LOG] OTP Code for {to_email}: {otp}")
        return True

    subject = "EDRP Registration Verification"
    body_html = f"""
    <html>
    <head></head>
    <body style="font-family: sans-serif; font-size: 14px; color: #333;">
        <p>Hello,</p>
        <p>Thank you for registering on the Expert Decision Replay Platform.</p>
        <p>Your verification code is: <strong>{otp}</strong></p>
        <p>This code will expire in 2 minutes.</p>
        <br>
        <p>Best regards,<br>The EDRP Team</p>
    </body>
    </html>
    """
    body_text = f"Hello,\n\nThank you for registering on the Expert Decision Replay Platform.\n\nYour verification code is: {otp}\n\nThis code will expire in 2 minutes.\n\nBest regards,\nThe EDRP Team"

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr(('EDRP Platform', SMTP_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Auto-Submitted'] = 'auto-generated'
    msg['Reply-To'] = SMTP_EMAIL
    
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP send note ({e}). Fallback [OTP LOG] OTP Code for {to_email}: {otp}")
        return True

def send_id_email(to_email: str, employee_id: str):
    """
    Sends the generated employee ID to the user's email address.
    """
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print("SMTP_EMAIL or SMTP_APP_PASSWORD not set in .env; skipping email notification.")
        return False

    subject = "EDRP Account Information"
    body_html = f"""
    <html>
    <head></head>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
        <p>Hello,</p>
        <p>Your registration for the Expert Decision Replay Platform has been processed.</p>
        <p>Your generated Login ID is: <strong>{employee_id}</strong></p>
        <p>Please keep this ID safe as you will need it to access your account.</p>
        <br>
        <p>Best regards,<br>The EDRP Team</p>
    </body>
    </html>
    """
    body_text = f"Hello,\n\nYour registration for the Expert Decision Replay Platform has been processed.\n\nYour generated Login ID is: {employee_id}\n\nPlease keep this ID safe as you will need it to access your account.\n\nBest regards,\nThe EDRP Team"

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr(('EDRP Support', SMTP_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Auto-Submitted'] = 'auto-generated'
    
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=3.0)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send ID email: {e}")
        return False


def send_account_approved_email(to_email: str, employee_id: str, full_name: str = ""):
    """
    Sends account approval confirmation email to the user when an Administrator approves their account.
    """
    name_str = f" {full_name}" if full_name else ""
    print(f"[EMAIL LOG] Account Approved Email for {to_email} ({employee_id})")

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in SMTP_EMAIL.lower() or "your_" in SMTP_APP_PASSWORD.lower():
        return True

    subject = "EDRP Account Approved - You Can Now Login"
    body_html = f"""
    <html>
    <head></head>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
        <p>Hello{name_str},</p>
        <p>Great news! Your account on the <strong>Expert Decision Replay Platform (EDRP)</strong> has been approved by the Administrator.</p>
        <p>Your account has been verified and you can now log in using your credentials:</p>
        <ul>
            <li><strong>Employee ID / Login ID:</strong> {employee_id}</li>
        </ul>
        <p>You may now log in to the platform at any time using your Employee ID and password.</p>
        <br>
        <p>Best regards,<br><strong>The EDRP Administrator & Support Team</strong></p>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nGreat news! Your account on the Expert Decision Replay Platform (EDRP) has been approved by the Administrator.\n\nYour account has been verified and you can now log in using your credentials:\nEmployee ID / Login ID: {employee_id}\n\nYou may now log in to the platform at any time using your Employee ID and password.\n\nBest regards,<br>The EDRP Administrator & Support Team"

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr(('EDRP Support', SMTP_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Auto-Submitted'] = 'auto-generated'

    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send account approved email to {to_email}: {e}")
        return False


def _is_email_enabled_in_settings() -> bool:
    try:
        from app.database.connection import SessionLocal
        from app.models.system_setting import SystemSetting
        db = SessionLocal()
        setting = db.query(SystemSetting).first()
        enabled = setting.enable_email_notifications if setting else True
        db.close()
        return enabled
    except Exception as e:
        return True

def _send_smtp_mail(to_email: str, subject: str, body_text: str):
    if not _is_email_enabled_in_settings():
        print(f"[EMAIL DISPATCH DISABLED VIA SETTINGS] To: {to_email} | Subject: {subject}")
        return True

    print(f"[EMAIL DISPATCH] To: {to_email} | Subject: {subject}")
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in str(SMTP_EMAIL).lower() or "your_" in str(SMTP_APP_PASSWORD).lower():
        print(f"[EMAIL CONSOLE LOG] Body:\n{body_text}")
        return True

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr(('EDRP Support', SMTP_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)

    msg.attach(MIMEText(body_text, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP dispatch note: {e}")
        return False
