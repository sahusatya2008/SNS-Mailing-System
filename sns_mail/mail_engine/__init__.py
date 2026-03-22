"""
Mail Engine Module

This module provides email sending functionality for SNS Mail.
"""

from .smtp_server import send_email, send_notification, send_security_alert

__all__ = ['send_email', 'send_notification', 'send_security_alert']