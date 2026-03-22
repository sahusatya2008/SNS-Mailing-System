import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import logging
from datetime import datetime
from flask import current_app
from ..security.engine import SecurityEngine
from ..database.models import VirusScanLog
from .. import db

def send_email(sender_email, recipient_email, subject, body, attachment_path=None):
    """
    Send email using SMTP
    
    Args:
        sender_email (str): Sender's email address
        recipient_email (str): Recipient's email address
        subject (str): Email subject
        body (str): Email body
        attachment_path (str): Path to attachment file
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add body to email
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            # Scan attachment for viruses
            security_engine = SecurityEngine()
            scan_result = security_engine.scan_file(attachment_path)
            
            if scan_result['infected']:
                logging.warning(f"Virus detected in attachment: {scan_result['virus_name']}")
                
                # Log virus scan result
                virus_log = VirusScanLog(
                    filename=os.path.basename(attachment_path),
                    file_path=attachment_path,
                    scan_result='INFECTED',
                    virus_name=scan_result['virus_name'],
                    scanned_at=datetime.utcnow()
                )
                db.session.add(virus_log)
                db.session.commit()
                
                return False
            
            # Add clean attachment
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(attachment_path)}'
            )
            msg.attach(part)
        
        # Send email
        text = msg.as_string()
        
        # For development, we'll use a local SMTP server
        # In production, this would connect to a real SMTP server
        with smtplib.SMTP('localhost', 1025) as server:
            server.sendmail(sender_email, recipient_email, text)
        
        logging.info(f"Email sent successfully from {sender_email} to {recipient_email}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return False

def send_notification(recipient_email, subject, message):
    """
    Send notification email
    
    Args:
        recipient_email (str): Recipient's email address
        subject (str): Email subject
        message (str): Notification message
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEText(message, 'plain')
        msg['From'] = 'noreply@snsx.com'
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Send email
        with smtplib.SMTP('localhost', 1025) as server:
            server.sendmail('noreply@snsx.com', recipient_email, msg.as_string())
        
        logging.info(f"Notification sent to {recipient_email}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending notification: {e}")
        return False

def send_security_alert(recipient_email, alert_type, details):
    """
    Send security alert email
    
    Args:
        recipient_email (str): Recipient's email address
        alert_type (str): Type of security alert
        details (str): Alert details
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = f"Security Alert: {alert_type}"
    message = f"""
Security Alert Detected

Alert Type: {alert_type}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Details: {details}

Please review your account security settings and take appropriate action.

If you believe this is a false positive, please contact support.

SNS Mail Security Team
"""
    
    return send_notification(recipient_email, subject, message)

def send_account_notification(user_email, action, details):
    """
    Send account-related notification
    
    Args:
        user_email (str): User's email address
        action (str): Account action (e.g., 'password_changed', 'login_failed')
        details (str): Action details
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if action == 'password_changed':
        subject = "Password Changed Successfully"
        message = f"""
Your SNS Mail account password has been changed successfully.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}

If you did not make this change, please contact support immediately.

SNS Mail Team
"""
    
    elif action == 'login_failed':
        subject = "Failed Login Attempt"
        message = f"""
There was a failed login attempt to your SNS Mail account.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}
Attempted Username: {details.get('username', 'Unknown')}

If this was not you, please secure your account immediately.

SNS Mail Security Team
"""
    
    elif action == 'account_locked':
        subject = "Account Temporarily Locked"
        message = f"""
Your SNS Mail account has been temporarily locked due to multiple failed login attempts.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}

Your account will be automatically unlocked after 30 minutes.
If you need immediate assistance, please contact support.

SNS Mail Security Team
"""
    
    else:
        return False
    
    return send_notification(user_email, subject, message)

def send_welcome_email(user_email, username):
    """
    Send welcome email to new user
    
    Args:
        user_email (str): User's email address
        username (str): User's username
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Welcome to SNS Mail!"
    message = f"""
Welcome to SNS Mail, {username}!

Your account has been successfully created. Here are some important details:

Email: {user_email}
Username: {username}
Domain: @snsx.com

Security Features:
- Two-Factor Authentication (2FA) available
- QR Code scanning for secure contact sharing
- Advanced virus scanning for all attachments
- Biometric authentication (face and eye scan)

Getting Started:
1. Set up 2FA in your account settings for enhanced security
2. Generate your personal QR code to share your email address securely
3. Upload your face photo and eye scan for biometric authentication
4. Explore the dashboard and customize your experience

Need Help?
Visit our help center or contact support for assistance.

Welcome to the SNS Mail community!

SNS Mail Team
"""
    
    return send_notification(user_email, subject, message)

def send_2fa_notification(user_email, action, details):
    """
    Send 2FA-related notification
    
    Args:
        user_email (str): User's email address
        action (str): 2FA action (e.g., 'enabled', 'disabled', 'failed')
        details (dict): Action details
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if action == 'enabled':
        subject = "Two-Factor Authentication Enabled"
        message = f"""
Two-Factor Authentication has been enabled on your SNS Mail account.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}

Your account is now more secure. You will need to provide a 2FA code when logging in.

SNS Mail Security Team
"""
    
    elif action == 'disabled':
        subject = "Two-Factor Authentication Disabled"
        message = f"""
Two-Factor Authentication has been disabled on your SNS Mail account.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}

For your security, we recommend re-enabling 2FA. You can do this in your account settings.

SNS Mail Security Team
"""
    
    elif action == 'failed':
        subject = "Two-Factor Authentication Failed"
        message = f"""
There was a failed Two-Factor Authentication attempt on your SNS Mail account.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {details.get('ip_address', 'Unknown')}
2FA Code: {details.get('code', 'Unknown')}

If this was not you, please secure your account immediately.

SNS Mail Security Team
"""
    
    else:
        return False
    
    return send_notification(user_email, subject, message)