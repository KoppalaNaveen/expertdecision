import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import dns.resolver

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
_raw_password = os.getenv("SMTP_APP_PASSWORD", "")
SMTP_APP_PASSWORD = _raw_password.replace(" ", "") if _raw_password else ""
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Global toggles to silence unsolicited automated/routine emails
ENABLE_ROUTINE_EMAILS = os.getenv("ENABLE_ROUTINE_EMAILS", "false").strip().lower() in ("true", "1", "yes")
ENABLE_SECURITY_EMAILS = os.getenv("ENABLE_SECURITY_EMAILS", "false").strip().lower() in ("true", "1", "yes")
ENABLE_NOTIFICATION_EMAILS = os.getenv("ENABLE_NOTIFICATION_EMAILS", "false").strip().lower() in ("true", "1", "yes")

# In-memory deliverability cache for domain MX lookups
_DOMAIN_MX_CACHE: dict[str, bool] = {}

_KNOWN_VALID_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.ca", "yahoo.com.au",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "zoho.com", "aol.com", "mail.com", "gmx.com", "yandex.com", "fastmail.com"
}

_BLOCKED_MOCK_DOMAINS = {
    "localhost", "invalid", "test.invalid", "rw.com", "emp.com", "mgr.com", "adm.com",
    "rev.com", "usr.com", "org.com", "dev.com", "qa.com", "test.com", "example.com",
    "example.org", "example.net", "sample.com", "dummy.com", "mock.com", "fake.com",
    "temp.com", "xyz.com", "domain.com", "company.com", "mailinator.com", "yopmail.com",
    "trashmail.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "dispostable.com",
    "sharklasers.com", "getairmail.com", "none.com", "null.com"
}

_BLOCKED_TLDS = (
    ".test", ".invalid", ".localhost", ".example", ".local", ".internal",
    ".mock", ".fake", ".dummy", ".sample", ".localdomain", ".lan"
)

def _has_valid_mx_records(domain: str) -> bool:
    """
    Checks if a domain has valid, active Mail Exchange (MX) DNS records.
    Prevents SMTP transmission to non-existent or unresolvable domains (which cause Mail Delivery Subsystem bounce emails).
    """
    d = (domain or "").strip().lower()
    if not d or "." not in d:
        return False
    if d in _KNOWN_VALID_DOMAINS:
        return True
    if d in _BLOCKED_MOCK_DOMAINS or any(d.endswith(tld) for tld in _BLOCKED_TLDS):
        return False
    if d in _DOMAIN_MX_CACHE:
        return _DOMAIN_MX_CACHE[d]

    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']
        resolver.lifetime = 2.5
        resolver.timeout = 2.5
        answers = resolver.resolve(d, 'MX')
        if len(answers) > 0:
            _DOMAIN_MX_CACHE[d] = True
            return True
    except Exception:
        pass

    _DOMAIN_MX_CACHE[d] = False
    return False

def is_deliverable_email(email_str: str) -> bool:
    """
    Validates if an email address has a valid recipient structure AND a resolvable, deliverable mail domain.
    Prevents Gmail Mail Delivery Subsystem DNS timeout / DEADLINE_EXCEEDED bounces.
    """
    if not email_str or not isinstance(email_str, str):
        return False
    clean = email_str.strip().lower()
    if "@" not in clean or "." not in clean:
        return False
    parts = clean.split("@")
    if len(parts) != 2:
        return False
    user_part, domain_part = parts[0].strip(), parts[1].strip()
    if not domain_part or not user_part:
        return False
    if len(user_part) < 1 or len(domain_part) < 4:
        return False
    # Check for invalid characters
    if any(c in user_part for c in " \t\r\n<>(),;:[]\\\""):
        return False
    if any(c in domain_part for c in " \t\r\n<>(),;:[]\\\""):
        return False
    return _has_valid_mx_records(domain_part)

def send_otp_email(to_email: str, otp: str):
    """
    Sends a 6-digit OTP to the user's email address using Gmail SMTP.
    Fallback prints OTP to console if SMTP credentials are missing, deliverability fails, or server connection fails.
    """
    if not is_deliverable_email(to_email):
        print(f"[OTP LOG - MOCK RECIPIENT] OTP Code for {to_email}: {otp}")
        return True

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
    if not is_deliverable_email(to_email):
        print(f"[ID LOG - MOCK RECIPIENT] Employee ID for {to_email}: {employee_id}")
        return True

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


def get_recipient_email(user) -> str:
    """
    Safely extracts the human-readable registered email address for a User object.
    Prefers email_original if available, or email if it contains '@'.
    """
    if not user:
        return None
    orig = getattr(user, 'email_original', None)
    if orig and '@' in str(orig):
        candidate = str(orig).strip().lower()
        if candidate and '@' in candidate and '.' in candidate:
            return candidate
    em = getattr(user, 'email', None)
    if em and '@' in str(em):
        candidate = str(em).strip().lower()
        if candidate and '@' in candidate and '.' in candidate:
            return candidate
    return None


def send_account_approved_email(to_email: str, employee_id: str, full_name: str = "", role_name: str = "", team_name: str = "", designation: str = "", approved_by: str = "Administrator") -> bool:
    """
    Automated Account Email -> Sent when an Administrator approves a pending account.
    Notifies the user that their account is verified and approved, and includes their team, designation, and admin details.
    """
    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    name_str = f" {full_name}" if full_name else ""
    subject = "Your Account is Verified and Approved - EDRP Platform"
    
    role_item = f'<div style="margin-bottom: 6px;"><strong>Assigned Role:</strong> {role_name}</div>' if role_name else ''
    team_item = f'<div style="margin-bottom: 6px;"><strong>Assigned Team:</strong> {team_name}</div>' if team_name else ''
    desig_item = f'<div style="margin-bottom: 6px;"><strong>Designation:</strong> {designation}</div>' if designation else ''
    approver_item = f'<div style="margin-bottom: 6px;"><strong>Approved By:</strong> {approved_by}</div>' if approved_by else ''

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); }}
            .header {{ background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); color: #ffffff; padding: 28px 24px; text-align: center; }}
            .content {{ padding: 28px 24px; }}
            .badge-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; border-radius: 8px; padding: 16px; margin: 20px 0; }}
            .btn-login {{ display: inline-block; background: #16a34a; color: #ffffff !important; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 8px; margin: 16px 0; }}
            .footer {{ border-top: 1px solid #f1f5f9; padding: 16px 24px; background: #f8fafc; font-size: 12px; color: #64748b; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div style="font-size: 28px; margin-bottom: 6px;">🎉</div>
                <h1 style="margin: 0; font-size: 20px; font-weight: 800; color: #ffffff;">Account Verified & Approved</h1>
                <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9; color: #dcfce7;">Expert Decision Replay Platform</p>
            </div>
            <div class="content">
                <p style="font-size: 15px; margin-top: 0;">Hello<strong>{name_str}</strong>,</p>
                <p style="color: #334155;">Great news! <strong>Your account has been verified and approved by the Administrator.</strong></p>
                <p style="color: #334155;">You can now log in to the platform through your assigned corporate credentials.</p>
                
                <div class="badge-box">
                    <div style="font-size: 11px; font-weight: 800; color: #166534; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">Your Official Profile & Assignment</div>
                    <div style="margin-bottom: 6px;"><strong>Full Name:</strong> {full_name or 'User'}</div>
                    <div style="margin-bottom: 6px;"><strong>Employee ID / Login ID:</strong> <span style="background: #ffffff; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 4px; font-weight: 700; color: #15803d;">{employee_id}</span></div>
                    <div style="margin-bottom: 6px;"><strong>Registered Email:</strong> {clean_email}</div>
                    {role_item}
                    {team_item}
                    {desig_item}
                    {approver_item}
                    <div style="margin-bottom: 0;"><strong>Account Status:</strong> <span style="color: #16a34a; font-weight: 700;">✓ Verified & Active</span></div>
                </div>

                <div style="text-align: center;">
                    <a href="http://localhost:5000/login" class="btn-login">Log In to Your Account →</a>
                </div>

                <p style="font-size: 13px; color: #64748b; margin-top: 16px;">
                    Use your <strong>Employee ID</strong> (or registered email) along with your password to access your dashboard.
                </p>
            </div>
            <div class="footer">
                <p style="margin: 0;">Need assistance? Contact your System Administrator or Support Team.</p>
                <p style="margin: 4px 0 0; font-weight: 600; color: #475569;">Expert Decision Replay Platform (EDRP)</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body_text = f"""Hello{name_str},

Great news! Your account has been verified and approved by the Administrator.
You can now log in to your account through your login credentials.

Account Details:
- Employee ID / Login ID: {employee_id}
- Registered Email: {clean_email}
- Status: Verified & Active

Login URL: http://localhost:5000/login

Please sign in using your Employee ID (or registered email) and password.

Regards,
EDRP Administration & Support Team
"""

    return _dispatch_original_gmail(clean_email, subject, body_html, body_text, "EDRP Support")


def _dispatch_original_gmail(to_email: str, subject: str, body_html: str, body_text: str, sender_label: str = "EDRP Security") -> bool:
    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    # Block mock / non-deliverable email domains from triggering real SMTP network calls
    if not is_deliverable_email(clean_email):
        print(f"[{sender_label.upper()} - MOCK RECIPIENT SKIPPED] Prevented sending '{subject}' to dummy address: {clean_email}")
        return True

    # Essential account emails (OTP, password reset, account approval/credentials) are always permitted
    is_essential_account_email = any(k.lower() in subject.lower() for k in [
        "verification", "password reset", "credentials", "security notice", 
        "approved", "verified", "account application", "account status", "registration"
    ])

    # If security and routine emails are disabled, silence non-essential background emails
    if not is_essential_account_email and not ENABLE_SECURITY_EMAILS and not ENABLE_ROUTINE_EMAILS:
        print(f"[{sender_label.upper()} - AUTOMATED EMAIL SILENCED] Prevented sending '{subject}' to {clean_email}")
        return True

    # Check system setting for non-essential emails
    if not is_essential_account_email and not _is_email_enabled_in_settings():
        print(f"[{sender_label.upper()} - EMAIL DISABLED IN SETTINGS] Skipping '{subject}' to {clean_email}")
        return True


    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in str(SMTP_EMAIL).lower() or "your_" in str(SMTP_APP_PASSWORD).lower():
        print(f"[{sender_label.upper()} LOG] To: {clean_email} | Subject: {subject}\n{body_text}")
        return True

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr((sender_label, SMTP_EMAIL))
    msg['To'] = clean_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Auto-Submitted'] = 'auto-generated'
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[ORIGINAL GMAIL DELIVERED] Successfully sent '{subject}' to {clean_email}")
        return True
    except Exception as e:
        print(f"[ORIGINAL GMAIL ERROR] Failed to send '{subject}' to {clean_email}: {e}")
        return False


def _send_smtp_mail(to_email: str, subject: str, body: str) -> bool:
    return _dispatch_original_gmail(
        to_email=to_email,
        subject=subject,
        body_html=f"<div style='font-family: Arial, sans-serif; padding: 20px; line-height: 1.6;'><p>{body.replace(chr(10), '<br>')}</p></div>",
        body_text=body,
        sender_label="EDRP Support"
    )


def send_critical_security_email(to_email: str, recipient_name: str, subject: str, message: str) -> bool:
    """
    Critical/System Email -> Sends security alerts and administrative notices via Original Gmail.
    """
    if not ENABLE_SECURITY_EMAILS:
        print(f"[SECURITY EMAIL SILENCED] Security alert skipped for {to_email}: {subject}")
        return True

    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    name_str = f" {recipient_name}" if recipient_name else ""
    full_subject = f"[SECURITY] {subject}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #dc2626; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">EDRP Security Alert</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    {message}
                </div>
                <p style="font-size: 12px; color: #64748b;">If this was not you, please immediately notify your System Administrator.</p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\n[SECURITY ALERT]\n{message}\n\nExpert Decision Replay Platform"
    return _dispatch_original_gmail(clean_email, full_subject, body_html, body_text, "EDRP Security")


def send_password_changed_email(to_email: str, recipient_name: str, change_time: str = None) -> bool:
    """
    Automated Security Email -> Sent after successful password update.
    """
    if not ENABLE_SECURITY_EMAILS:
        print(f"[PASSWORD CHANGED LOG - SILENCED] Password change email skipped for {to_email}")
        return True

    from datetime import datetime, timezone
    time_str = change_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    subject = "Your EDRP account password was changed"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #0284c7; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Password Changed Successfully</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>Your EDRP account password was changed successfully.</p>
                <div style="background: #f0f9ff; border-left: 4px solid #0284c7; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <div><strong>Status:</strong> Password successfully updated</div>
                    <div style="margin-top: 4px;"><strong>Date & Time:</strong> {time_str}</div>
                </div>
                <p style="color: #dc2626; font-size: 13px;">
                    <strong>Security Warning:</strong> If you did not perform this change, please immediately contact your Administrator or EDRP Support via the Support Center to secure your account.
                </p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Security Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour EDRP account password was changed successfully.\nDate/Time: {time_str}\n\nIf you did not perform this change, please contact your Administrator or Support immediately.\n\nRegards,\nEDRP Security Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Security")


def send_password_reset_confirmation_email(to_email: str, recipient_name: str, reset_time: str = None) -> bool:
    """
    Automated Security Email -> Sent after successful password reset completion.
    """
    if not ENABLE_SECURITY_EMAILS:
        print(f"[PASSWORD RESET LOG - SILENCED] Password reset email skipped for {to_email}")
        return True

    from datetime import datetime, timezone
    time_str = reset_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    subject = "Your EDRP password was reset"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #0284c7; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Password Reset Confirmation</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>Your EDRP password reset was completed successfully.</p>
                <div style="background: #f0f9ff; border-left: 4px solid #0284c7; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <div><strong>Status:</strong> Password reset complete</div>
                    <div style="margin-top: 4px;"><strong>Date & Time:</strong> {time_str}</div>
                </div>
                <p style="color: #dc2626; font-size: 13px;">
                    <strong>Security Warning:</strong> If you did not request or perform this password reset, please contact your Administrator immediately.
                </p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Security Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour EDRP password was reset successfully.\nDate/Time: {time_str}\n\nIf you did not perform this action, please contact your Administrator immediately.\n\nRegards,\nEDRP Security Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Security")


def send_new_login_email(to_email: str, recipient_name: str, login_time: str = None, device_info: str = "Web Browser Session", ip_address: str = None) -> bool:
    """
    Automated Security Email -> Sent upon successful login detection.
    """
    if not ENABLE_SECURITY_EMAILS:
        print(f"[LOGIN ALERT SILENCED] Login notification email skipped for {to_email}")
        return True

    from datetime import datetime, timezone
    time_str = login_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    subject = "New login detected on your EDRP account"
    ip_line = f"<div><strong>IP Address:</strong> {ip_address}</div>" if ip_address else ""
    ip_text = f"IP Address: {ip_address}\n" if ip_address else ""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #1e293b; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">New Login Alert</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>A new sign-in was detected on your Expert Decision Replay Platform account.</p>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 14px; border-radius: 8px; margin: 16px 0;">
                    <div><strong>Date & Time:</strong> {time_str}</div>
                    <div><strong>Application:</strong> Expert Decision Replay Platform (EDRP)</div>
                    <div><strong>Session / Platform:</strong> {device_info}</div>
                    {ip_line}
                </div>
                <p style="font-size: 12px; color: #64748b;">If this was you, no action is needed. If you did not recognize this login, please change your password immediately.</p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Security Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nA new login was detected on your EDRP account.\nTime: {time_str}\nPlatform: EDRP\nSession: {device_info}\n{ip_text}\nIf this was not you, change your password immediately.\n\nRegards,\nEDRP Security Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Security")


def send_account_rejected_email(to_email: str, recipient_name: str, reason: str = None) -> bool:
    """
    Automated Account Email -> Sent when an Administrator rejects a pending account.
    """
    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    name_str = f" {recipient_name}" if recipient_name else ""
    subject = "Your EDRP account request was rejected"
    reason_html = f"<div><strong>Reason:</strong> {reason}</div>" if reason else ""
    reason_text = f"\nReason: {reason}" if reason else ""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #e11d48; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Account Application Update</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>Your registration request for the <strong>Expert Decision Replay Platform (EDRP)</strong> was not approved.</p>
                <div style="background: #fff1f2; border-left: 4px solid #e11d48; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <div><strong>Decision:</strong> Account Request Rejected</div>
                    {reason_html}
                </div>
                <p style="font-size: 12px; color: #64748b;">If you believe this is an error or need clarification, please contact your Organization Administrator.</p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Administration Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour EDRP account request was rejected.{reason_text}\n\nPlease contact your Organization Administrator for assistance.\n\nRegards,\nEDRP Administration Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Administration")


def send_account_deleted_email(to_email: str, recipient_name: str, deletion_time: str = None) -> bool:
    """
    Automated Account Email -> Sent when an account is permanently deleted.
    """
    if not ENABLE_ROUTINE_EMAILS:
        print(f"[ACCOUNT DELETED LOG - SILENCED] Account deleted email skipped for {to_email}")
        return True

    from datetime import datetime, timezone
    time_str = deletion_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    subject = "Your EDRP account has been deleted"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #475569; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Account Deletion Confirmation</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>This email confirms that your account on the <strong>Expert Decision Replay Platform (EDRP)</strong> has been permanently deleted.</p>
                <div style="background: #f1f5f9; border-left: 4px solid #475569; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <div><strong>Status:</strong> Account Permanently Deleted</div>
                    <div style="margin-top: 4px;"><strong>Date & Time:</strong> {time_str}</div>
                </div>
                <p style="font-size: 12px; color: #64748b;">All associated personal records and profile data have been permanently removed. If you have any questions, please contact Support.</p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>The EDRP Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour account on the Expert Decision Replay Platform has been permanently deleted.\nDate/Time: {time_str}\n\nRegards,\nThe EDRP Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Team")


def send_role_changed_email(to_email: str, recipient_name: str, prev_role: str, new_role: str, prev_emp_id: str = None, new_emp_id: str = None, change_time: str = None) -> bool:
    """
    Automated Account Email -> Sent when an Administrator changes/promotes a user's role and assigns a new Employee ID.
    """
    if not ENABLE_ROUTINE_EMAILS:
        print(f"[ROLE CHANGED LOG - SILENCED] Role changed email skipped for {to_email} ({prev_role} -> {new_role})")
        return True

    from datetime import datetime, timezone
    time_str = change_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    subject = f"Role Updated - Your New Employee ID is {new_emp_id}" if new_emp_id else "Your EDRP account role has been updated"

    id_change_section = ""
    id_text_section = ""
    if prev_emp_id and new_emp_id:
        id_change_section = f"""
        <div style="background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 8px; padding: 14px; margin-top: 12px;">
            <div style="font-size: 12px; color: #4338ca; font-weight: bold; text-transform: uppercase; margin-bottom: 6px;">Employee ID Update</div>
            <div style="display: flex; align-items: center; gap: 8px; font-size: 14px;">
                <span style="text-decoration: line-through; color: #6b7280; font-family: monospace;">{prev_emp_id}</span>
                <span style="color: #4338ca; font-weight: bold;">&rarr;</span>
                <span style="color: #1e1b4b; font-weight: 800; font-family: monospace; font-size: 16px; background: #ffffff; padding: 2px 8px; border-radius: 4px; border: 1px solid #a5b4fc;">{new_emp_id}</span>
            </div>
            <div style="font-size: 12px; color: #4b5563; margin-top: 8px;">
                <strong>Important:</strong> Your login Employee ID has changed from <strong>{prev_emp_id}</strong> to <strong>{new_emp_id}</strong>. Please use <strong>{new_emp_id}</strong> along with your existing password to sign in.
            </div>
        </div>
        """
        id_text_section = f"\nEmployee ID Change: {prev_emp_id} -> {new_emp_id}\nImportant: Please sign in with your new Employee ID: {new_emp_id}\n"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #7c3aed; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Role Assignment & Employee ID Update</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>An Administrator has updated your assigned role on the <strong>Expert Decision Replay Platform (EDRP)</strong>.</p>
                <div style="background: #f5f3ff; border: 1px solid #ddd6fe; padding: 14px; border-radius: 8px; margin: 16px 0;">
                    <div><strong>Previous Role:</strong> {prev_role}</div>
                    <div style="margin-top: 6px;"><strong>New Role:</strong> <span style="color: #7c3aed; font-weight: bold;">{new_role}</span></div>
                    <div style="margin-top: 6px; font-size: 12px; color: #64748b;"><strong>Date & Time:</strong> {time_str}</div>
                </div>
                {id_change_section}
                <p style="font-size: 12px; color: #64748b; margin-top: 16px;">Your workspace access and permissions have been updated to reflect your new role.</p>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Administration Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour EDRP account role has been updated by an Administrator.\nPrevious Role: {prev_role}\nNew Role: {new_role}\n{id_text_section}Date/Time: {time_str}\n\nRegards,\nEDRP Administration Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Administration")


def send_decision_outcome_email(to_email: str, recipient_name: str, decision_id: int, decision_title: str, status: str, reviewer_name: str = "Reviewer", comments: str = None, decision_date: str = None) -> bool:
    """
    Decision Outcome Email -> Sent when a decision is Accepted (Approved) or Rejected by reviewers/managers.
    Delivers directly to user's registered Gmail account.
    """
    if not ENABLE_NOTIFICATION_EMAILS or not _is_email_enabled_in_settings():
        print(f"[DECISION OUTCOME LOG - SILENCED] Outcome email skipped for DEC-{decision_id} to {to_email}")
        return True

    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    from datetime import datetime, timezone
    time_str = decision_date or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    is_accepted = str(status).strip().lower() in ["approved", "accepted"]

    theme_color = "#16a34a" if is_accepted else "#dc2626"
    bg_light = "#f0fdf4" if is_accepted else "#fef2f2"
    border_color = "#bbf7d0" if is_accepted else "#fecaca"
    status_label = "Accepted & Approved" if is_accepted else "Rejected"
    header_title = "Decision Accepted" if is_accepted else "Decision Rejected"
    subject = f"[EDRP] Decision {status_label}: DEC-{decision_id} - {decision_title}"

    comment_section = ""
    comment_text = ""
    if comments and comments.strip():
        comment_section = f"""
        <div style="background: {bg_light}; border-left: 4px solid {theme_color}; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <div style="font-size: 12px; font-weight: bold; color: {theme_color}; text-transform: uppercase;">Reviewer Feedback / Comments:</div>
            <div style="margin-top: 6px; font-size: 13.5px; color: #1e293b; white-space: pre-wrap;">{comments}</div>
        </div>
        """
        comment_text = f"\nReviewer Feedback: {comments}\n"

    next_step_msg = (
        "Your decision has been officially approved and published in the system repository."
        if is_accepted
        else "Please review the reviewer comments above, make the necessary revisions, and resubmit the decision for review."
    )

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6; background: #f8fafc; padding: 20px 0;">
        <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
            <div style="background: {theme_color}; color: #ffffff; padding: 20px 24px;">
                <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.9;">Decision Review Update</div>
                <h2 style="margin: 4px 0 0 0; font-size: 18px; font-weight: 700;">{header_title}</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>Your submitted decision has been <strong>{status_label.lower()}</strong> by <strong>{reviewer_name}</strong>.</p>
                
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 12px; color: #64748b;">Decision ID:</span>
                        <span style="font-family: monospace; font-weight: bold; color: #0f172a;">DEC-{decision_id}</span>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 12px; color: #64748b;">Title:</span>
                        <div style="font-weight: 700; color: #0f172a; margin-top: 2px;">{decision_title}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 12px; color: #64748b;">Status:</span>
                        <span style="font-weight: bold; color: {theme_color};">{status_label}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 12px; color: #64748b;">Reviewed By:</span>
                        <span style="color: #334155; font-weight: 600;">{reviewer_name}</span>
                    </div>
                </div>

                {comment_section}

                <div style="background: #f1f5f9; padding: 12px 16px; border-radius: 6px; font-size: 12.5px; color: #475569; margin-top: 16px;">
                    <strong>Next Steps:</strong> {next_step_msg}
                </div>

                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>Expert Decision Replay Platform (EDRP)</strong></p>
            </div>
            <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 12px 24px; font-size: 11px; color: #94a3b8; text-align: center;">
                This is an automated notification sent to your registered Gmail account.
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"Hello{name_str},\n\nYour decision DEC-{decision_id}: '{decision_title}' has been {status_label.upper()}.\n\nReviewed By: {reviewer_name}\nStatus: {status_label}\nDate/Time: {time_str}\n{comment_text}\nNext Steps: {next_step_msg}\n\nExpert Decision Replay Platform"
    return _dispatch_original_gmail(clean_email, subject, body_html, body_text, "EDRP Decisions")


def send_account_status_email(to_email: str, recipient_name: str, is_active: bool, change_time: str = None) -> bool:
    """
    Automated Account Email -> Sent when an Administrator activates or deactivates an account.
    """
    if not ENABLE_ROUTINE_EMAILS:
        print(f"[ACCOUNT STATUS LOG - SILENCED] Status email skipped for {to_email} (Active={is_active})")
        return True

    from datetime import datetime, timezone
    time_str = change_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name_str = f" {recipient_name}" if recipient_name else ""
    status_label = "Activated" if is_active else "Deactivated"
    subject = f"Your EDRP account has been {status_label.lower()}"
    theme_color = "#16a34a" if is_active else "#ea580c"
    
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: {theme_color}; color: #ffffff; padding: 20px;">
                <h2 style="margin: 0; font-size: 18px;">Account Status: {status_label}</h2>
            </div>
            <div style="padding: 24px;">
                <p>Hello{name_str},</p>
                <p>Your account on the <strong>Expert Decision Replay Platform</strong> has been <strong>{status_label.lower()}</strong> by an Administrator.</p>
                <div style="background: #f8fafc; border-left: 4px solid {theme_color}; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <div><strong>Status:</strong> {status_label}</div>
                    <div style="margin-top: 4px;"><strong>Date & Time:</strong> {time_str}</div>
                    <div style="margin-top: 6px;">{'You now have full access to sign in and use the platform according to your assigned role and permissions.' if is_active else 'Your access to the platform has been deactivated. Please contact your Administrator if you believe this was done in error.'}</div>
                </div>
                <br>
                <p style="font-size: 12px; color: #64748b;">Regards,<br><strong>EDRP Administration Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    body_text = f"Hello{name_str},\n\nYour EDRP account has been {status_label.lower()}.\nDate/Time: {time_str}\n\nRegards,\nEDRP Administration Team"
    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Administration")


def send_smtp_service_email(to_email: str, sender_name: str, subject: str, message: str, priority: str = "Medium", delivery_method: str = "smtp") -> bool:
    """
    User-Initiated Email -> Sends an internal user-composed email using the explicitly chosen delivery method:
    - delivery_method == "gmail": Uses Original Gmail delivery
    - delivery_method == "smtp": Uses Project SMTP Email Service delivery
    """
    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    is_gmail = (delivery_method or "smtp").lower() == "gmail"
    from_tag = "EDRP Gmail Service" if is_gmail else "EDRP SMTP Service"
    full_subject = f"[{'GMAIL' if is_gmail else 'SMTP'}] {subject}"

    if not is_deliverable_email(clean_email):
        print(f"[{from_tag.upper()} - MOCK RECIPIENT SKIPPED] Prevented sending to non-deliverable address: {clean_email}")
        return True

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
            .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; }}
            .header {{ background: {'#ea4335' if is_gmail else '#2563eb'}; color: #ffffff; padding: 20px 24px; }}
            .header h3 {{ margin: 0; font-size: 17px; }}
            .header p {{ margin: 4px 0 0 0; font-size: 12px; opacity: 0.9; }}
            .body {{ padding: 24px; font-size: 14px; line-height: 1.6; color: #334155; }}
            .meta {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
            .content {{ background: #f8fafc; border-left: 4px solid {'#ea4335' if is_gmail else '#2563eb'}; padding: 14px 16px; border-radius: 4px; font-size: 14px; color: #0f172a; white-space: pre-wrap; }}
            .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 24px; font-size: 11px; color: #64748b; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h3>{sender_name} via {from_tag}</h3>
                <p>Delivery Method: {'Original Gmail' if is_gmail else 'Project SMTP Email Service'} · Priority: {priority}</p>
            </div>
            <div class="body">
                <div class="meta">
                    <strong>Subject:</strong> {subject}
                </div>
                <div class="content">{message}</div>
            </div>
            <div class="footer">
                Expert Decision Replay Platform · Sent via {'Original Gmail' if is_gmail else 'Project SMTP Email Service'}
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"Message from {sender_name} via {from_tag}\n\nSubject: {subject}\nPriority: {priority}\n\n{message}\n\n---\nExpert Decision Replay Platform"

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in str(SMTP_EMAIL).lower() or "your_" in str(SMTP_APP_PASSWORD).lower():
        print(f"[{from_tag.upper()} LOG] To: {clean_email} | Subject: {full_subject}\n{message}")
        return True

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr((from_tag, SMTP_EMAIL))
    msg['To'] = clean_email
    msg['Subject'] = full_subject
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
        print(f"[{from_tag.upper()} DELIVERED] Successfully sent email to {clean_email}")
        return True
    except Exception as e:
        print(f"[{from_tag.upper()} ERROR] Failed to send email to {clean_email}: {e}")
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


def send_notification_email(to_email: str, recipient_name: str, subject: str, message: str, notification_type: str = "Notification") -> bool:
    """
    Sends a rich, production-grade HTML notification email to the user's real email address via SMTP.
    """
    if not ENABLE_NOTIFICATION_EMAILS or not _is_email_enabled_in_settings():
        print(f"[NOTIFICATION LOG - SILENCED] Skipping email to {to_email} for subject: {subject}")
        return True

    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    if not is_deliverable_email(clean_email):
        print(f"[NOTIFICATION SMTP - MOCK RECIPIENT SKIPPED] Prevented sending to non-deliverable address: {clean_email}")
        return True

    name_str = f" {recipient_name}" if recipient_name else ""
    full_subject = f"[EDRP] {subject}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
            .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; }}
            .header {{ background: #2563eb; color: #ffffff; padding: 20px 24px; }}
            .header h3 {{ margin: 0; font-size: 17px; }}
            .body {{ padding: 24px; font-size: 14px; line-height: 1.6; color: #334155; }}
            .badge {{ display: inline-block; padding: 4px 10px; background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 700; border-radius: 20px; text-transform: uppercase; margin-bottom: 12px; }}
            .content {{ background: #f8fafc; border-left: 4px solid #2563eb; padding: 14px 16px; border-radius: 4px; font-size: 14px; color: #0f172a; margin: 16px 0; }}
            .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 24px; font-size: 11px; color: #64748b; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h3>Expert Decision Replay Platform</h3>
            </div>
            <div class="body">
                <span class="badge">{notification_type}</span>
                <p>Hello{name_str},</p>
                <div class="content">{message}</div>
                <p style="font-size: 12px; color: #64748b;">You can manage your notification preferences anytime from Platform Settings.</p>
            </div>
            <div class="footer">
                &copy; 2026 Expert Decision Replay Platform. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"Hello{name_str},\n\n[{notification_type}]\n{message}\n\n---\nExpert Decision Replay Platform"

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or "your_" in str(SMTP_EMAIL).lower() or "your_" in str(SMTP_APP_PASSWORD).lower():
        print(f"[NOTIFICATION SMTP LOG] To: {clean_email} | Subject: {full_subject}\n{message}")
        return True

    import email.utils
    msg = MIMEMultipart("alternative")
    msg['From'] = email.utils.formataddr(('EDRP Notifications', SMTP_EMAIL))
    msg['To'] = clean_email
    msg['Subject'] = full_subject
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
        print(f"[NOTIFICATION SMTP DELIVERED] Successfully sent {notification_type} email to {clean_email}")
        return True
    except Exception as e:
        print(f"SMTP notification delivery note: {e}")
        return False


def send_credentials_updated_email(
    to_email: str,
    full_name: str,
    employee_id: str,
    email_changed: bool = False,
    old_email: str = "",
    new_email: str = "",
    password_changed: bool = False,
    new_password: str = "",
    is_old_inbox: bool = False
) -> bool:
    """
    Dispatches security notifications when an Administrator updates a user's email or password.
    Sent to both old and new email addresses with updated credential details.
    """
    clean_email = (to_email or "").strip()
    if not clean_email or "@" not in clean_email:
        return False

    name_str = f" {full_name}" if full_name else ""
    subject = "Security Notice: EDRP Account Credentials Updated by Administrator"

    changes_html = ""
    changes_text = ""

    if email_changed:
        changes_html += f"""
        <li style="margin-bottom: 8px;">
            <strong>Email Address Updated:</strong><br>
            <span style="color: #64748b;">Previous Email:</span> <code style="background: #f1f5f9; padding: 2px 4px; border-radius: 3px;">{old_email}</code><br>
            <span style="color: #059669; font-weight: 600;">New Primary Email:</span> <strong style="color: #059669;">{new_email}</strong>
        </li>
        """
        changes_text += f"\n- Email Address Updated: Previous: {old_email} -> New: {new_email}"

    if password_changed:
        pwd_display = f'<code style="background: #eef2ff; color: #4338ca; font-weight: 700; padding: 3px 8px; border-radius: 4px; font-size: 13.5px; border: 1px solid #c7d2fe;">{new_password}</code>' if new_password else '<em>(Reset by Administrator)</em>'
        changes_html += f"""
        <li style="margin-bottom: 8px;">
            <strong>Password Updated by Administrator:</strong><br>
            <span style="color: #64748b;">Previous Password:</span> <span style="font-family: monospace; color: #94a3b8;">•••••••• (Overwritten)</span><br>
            <span style="color: #4338ca; font-weight: 600;">New Login Password:</span> {pwd_display}
        </li>
        """
        changes_text += f"\n- Password: Previous: [Overwritten] -> New Password: {new_password if new_password else '[Reset]'}"


    notice_box = ""
    if is_old_inbox and email_changed:
        notice_box = f"""
        <div style="background: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; margin: 16px 0; border-radius: 4px; font-size: 13px; color: #92400e;">
            <strong>Notice for Previous Email Address:</strong> This inbox ({old_email}) will no longer receive routine account communications. Future notifications will be sent to <strong>{new_email}</strong>.
        </div>
        """

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #1e293b; line-height: 1.6; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1e293b, #0f172a); color: #ffffff; padding: 24px;">
                <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; font-weight: 700;">Security Notification</div>
                <h2 style="margin: 6px 0 0 0; font-size: 20px; font-weight: 700; color: #ffffff;">Account Credentials Updated</h2>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 15px;">Hello<strong>{name_str}</strong>,</p>
                <p>An <strong>Administrator</strong> has updated the credentials and access details for your account on the <strong>Expert Decision Replay Platform (EDRP)</strong>.</p>
                
                <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 18px 0;">
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 8px;">Account Details</div>
                    <div style="margin-bottom: 6px;"><strong>Employee ID / Login ID:</strong> <code style="background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-weight: 700; color: #0f172a;">{employee_id}</code></div>
                    <div style="margin-top: 10px;">
                        <strong>Applied Changes:</strong>
                        <ul style="margin: 8px 0 0 0; padding-left: 20px;">
                            {changes_html}
                        </ul>
                    </div>
                </div>

                {notice_box}

                <p style="margin-top: 20px; font-size: 13.5px;">You can now sign in to your dashboard using your Employee ID <code>{employee_id}</code> or updated email address along with your updated credentials.</p>
                
                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b;">
                    <p style="margin: 0 0 6px 0;"><strong>Security Note:</strong> If you did not authorize or expect this change, please immediately contact your platform system administrator.</p>
                    <p style="margin: 0;">Regards,<br><strong>EDRP Platform Security Team</strong></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"""Hello{name_str},

An Administrator has updated the credentials for your account on the Expert Decision Replay Platform (EDRP).

Account Details:
- Employee ID / Login ID: {employee_id}
Applied Changes:{changes_text}

You can now sign in using your Employee ID ({employee_id}) or new email with your updated credentials.

Security Note: If you did not authorize or expect this change, please contact your platform administrator immediately.

Regards,
EDRP Platform Security Team
"""

    return _dispatch_original_gmail(to_email, subject, body_html, body_text, "EDRP Security")

