"""
Background Scheduler for SNS Mail

This module provides background task scheduling for:
- Sending scheduled emails
- Processing self-destructing emails
- Sending follow-up reminders
"""

import threading
import time
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackgroundScheduler:
    """Background scheduler for periodic tasks"""
    
    def __init__(self, app=None):
        self.app = app
        self._running = False
        self._thread = None
        self.interval = 60  # Check every 60 seconds
    
    def init_app(self, app):
        """Initialize the scheduler with a Flask app"""
        self.app = app
    
    def start(self):
        """Start the background scheduler"""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Background scheduler started")
    
    def stop(self):
        """Stop the background scheduler"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Background scheduler stopped")
    
    def _run(self):
        """Main scheduler loop"""
        while self._running:
            try:
                with self.app.app_context():
                    self._process_tasks()
            except Exception as e:
                logger.error(f"Error in scheduler: {str(e)}")
            
            # Sleep for the interval
            time.sleep(self.interval)
    
    def _process_tasks(self):
        """Process all scheduled tasks"""
        self._send_scheduled_emails()
        self._process_self_destructing_emails()
        self._send_follow_up_reminders()
    
    def _send_scheduled_emails(self):
        """Send emails that are due"""
        from ..database.models import ScheduledEmail, User, Email
        from .. import db
        from ..mail_engine.smtp_server import send_email
        
        now = datetime.utcnow()
        
        # Find emails that are due to be sent
        due_emails = ScheduledEmail.query.filter(
            ScheduledEmail.is_sent == False,
            ScheduledEmail.is_cancelled == False,
            ScheduledEmail.scheduled_at <= now
        ).all()
        
        for scheduled in due_emails:
            try:
                # Find the recipient
                recipient = User.query.filter_by(email=scheduled.recipient_email).first()
                sender = User.query.get(scheduled.user_id)
                
                if recipient and sender:
                    # Create the email
                    email = Email(
                        subject=scheduled.subject,
                        body=scheduled.body,
                        sender_id=sender.id,
                        recipient_id=recipient.id,
                        attachment_path=scheduled.attachment_path,
                        attachment_filename=scheduled.attachment_filename
                    )
                    db.session.add(email)
                    
                    # Mark scheduled email as sent
                    scheduled.is_sent = True
                    scheduled.sent_at = now
                    
                    db.session.commit()
                    
                    # Try to send via SMTP (optional, internal system works without it)
                    try:
                        send_email(
                            sender_email=sender.email,
                            recipient_email=recipient.email,
                            subject=scheduled.subject,
                            body=scheduled.body,
                            attachment_path=scheduled.attachment_path
                        )
                    except Exception as e:
                        logger.warning(f"SMTP send failed for scheduled email {scheduled.id}: {str(e)}")
                    
                    logger.info(f"Sent scheduled email {scheduled.id}: {scheduled.subject}")
                else:
                    # Recipient not found, mark as sent anyway to avoid retrying forever
                    scheduled.is_sent = True
                    scheduled.sent_at = now
                    db.session.commit()
                    logger.warning(f"Scheduled email {scheduled.id} recipient not found: {scheduled.recipient_email}")
                    
            except Exception as e:
                logger.error(f"Failed to send scheduled email {scheduled.id}: {str(e)}")
                db.session.rollback()
    
    def _process_self_destructing_emails(self):
        """Process self-destructing emails"""
        from ..database.models import Email
        from .. import db
        
        now = datetime.utcnow()
        
        # Find emails that should be destructed
        # Either after read or at a specific time
        destruct_emails = Email.query.filter(
            Email.is_self_destructing == True,
            Email.destructed_at == None,
            db.or_(
                db.and_(Email.destruct_after_read == True, Email.is_read == True),
                db.and_(Email.destruct_at != None, Email.destruct_at <= now)
            )
        ).all()
        
        for email in destruct_emails:
            try:
                email.destructed_at = now
                # Optionally delete the content
                email.body = "[This email has self-destructed]"
                email.subject = "[Self-Destructed]"
                db.session.commit()
                logger.info(f"Self-destructed email {email.id}")
            except Exception as e:
                logger.error(f"Failed to self-destruct email {email.id}: {str(e)}")
                db.session.rollback()
    
    def _send_follow_up_reminders(self):
        """Send follow-up reminders"""
        from ..database.models import FollowUpReminder
        from .. import db
        
        now = datetime.utcnow()
        
        # Find reminders that are due
        due_reminders = FollowUpReminder.query.filter(
            FollowUpReminder.reminder_sent == False,
            FollowUpReminder.is_dismissed == False,
            FollowUpReminder.reminder_at <= now
        ).all()
        
        for reminder in due_reminders:
            try:
                # Mark as sent (the UI will handle showing the notification)
                reminder.reminder_sent = True
                reminder.sent_at = now
                db.session.commit()
                logger.info(f"Sent follow-up reminder {reminder.id}")
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {str(e)}")
                db.session.rollback()


# Global scheduler instance
scheduler = BackgroundScheduler()