from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pyotp
import qrcode
import os
from io import BytesIO
import base64
import secrets
import hashlib

from .. import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    face_photo = db.Column(db.String(200))
    eye_scan = db.Column(db.String(200))
    totp_secret = db.Column(db.String(16))
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_server_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)  # Blue tick verification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    # New unique features
    ai_preferences = db.Column(db.Text)  # JSON for AI learning preferences
    mood_tracking_enabled = db.Column(db.Boolean, default=True)
    focus_mode_enabled = db.Column(db.Boolean, default=False)
    focus_mode_until = db.Column(db.DateTime)
    
    # Relationships
    sent_emails = db.relationship('Email', foreign_keys='Email.sender_id', backref='sender', lazy='dynamic')
    received_emails = db.relationship('Email', foreign_keys='Email.recipient_id', backref='recipient', lazy='dynamic')
    drafts = db.relationship('Draft', backref='user', lazy='dynamic')
    sent_folders = db.relationship('SentFolder', backref='user', lazy='dynamic')
    important_folders = db.relationship('ImportantFolder', backref='user', lazy='dynamic')
    archive_folders = db.relationship('ArchiveFolder', backref='user', lazy='dynamic')
    deleted_folders = db.relationship('DeletedFolder', backref='user', lazy='dynamic')
    spam_folders = db.relationship('SpamFolder', backref='user', lazy='dynamic')
    notes = db.relationship('Note', backref='user', lazy='dynamic')
    tasks = db.relationship('Task', backref='user', lazy='dynamic')
    vault_items = db.relationship('VaultItem', backref='user', lazy='dynamic')
    email_analytics = db.relationship('EmailAnalytics', backref='user', lazy='dynamic')
    scheduled_emails = db.relationship('ScheduledEmail', backref='user', lazy='dynamic')
    mood_logs = db.relationship('MoodLog', backref='user', lazy='dynamic')
    focus_sessions = db.relationship('FocusSession', backref='user', lazy='dynamic')
    email_templates = db.relationship('EmailTemplate', backref='user', lazy='dynamic')
    
    def __init__(self, name, username, email, password):
        self.name = name
        self.username = username
        self.email = email
        self.set_password(password)
        self.totp_secret = pyotp.random_base32()
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_totp_uri(self):
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            self.email,
            issuer_name="SNS Mail"
        )
    
    def verify_totp(self, token):
        return pyotp.TOTP(self.totp_secret).verify(token)
    
    def get_qr_code(self):
        """Generate QR code for the user's email address"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.email)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def is_account_locked(self):
        """Check if account is locked due to too many login attempts"""
        return self.locked_until is not None and datetime.utcnow() < self.locked_until
    
    def check_and_lock_account(self):
        """Lock account if too many failed attempts"""
        if self.login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
            self.login_attempts = 0
            db.session.commit()
    
    def reset_login_attempts(self):
        """Reset login attempts counter"""
        self.login_attempts = 0
        self.locked_until = None
        db.session.commit()
    
    def ban_user(self, reason):
        """Ban user account"""
        self.is_banned = True
        self.ban_reason = reason
        db.session.commit()
    
    def unban_user(self):
        """Unban user account"""
        self.is_banned = False
        self.ban_reason = None
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.username}>'


class Email(db.Model):
    __tablename__ = 'emails'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    is_read = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    is_spam = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(200))
    attachment_filename = db.Column(db.String(100))
    virus_detected = db.Column(db.Boolean, default=False)
    
    # New unique features
    is_self_destructing = db.Column(db.Boolean, default=False)
    destruct_after_read = db.Column(db.Boolean, default=False)
    destruct_at = db.Column(db.DateTime)
    destructed_at = db.Column(db.DateTime)
    is_encrypted = db.Column(db.Boolean, default=False)
    encryption_key = db.Column(db.String(64))
    mood_score = db.Column(db.Float)  # AI-detected mood (-1 to 1)
    mood_label = db.Column(db.String(20))  # positive, negative, neutral
    ai_summary = db.Column(db.Text)  # AI-generated summary
    priority_score = db.Column(db.Float, default=0.5)  # 0-1 priority
    read_duration = db.Column(db.Integer)  # seconds spent reading
    is_pinned = db.Column(db.Boolean, default=False)
    pinned_at = db.Column(db.DateTime)
    follow_up_reminder = db.Column(db.DateTime)
    follow_up_sent = db.Column(db.Boolean, default=False)
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def toggle_important(self):
        self.is_important = not self.is_important
        db.session.commit()
    
    def delete_email(self):
        self.is_deleted = True
        db.session.commit()
    
    def mark_as_spam(self):
        self.is_spam = True
        db.session.commit()
    
    def check_self_destruct(self):
        """Check if email should be self-destructed"""
        if self.is_self_destructing:
            if self.destruct_after_read and self.is_read:
                return True
            if self.destruct_at and datetime.utcnow() >= self.destruct_at:
                return True
        return False
    
    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.pinned_at = datetime.utcnow() if self.is_pinned else None
        db.session.commit()
    
    def __repr__(self):
        return f'<Email {self.subject}>'


class Draft(db.Model):
    __tablename__ = 'drafts'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attachment_path = db.Column(db.String(200))
    attachment_filename = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<Draft {self.subject}>'


class SentFolder(db.Model):
    __tablename__ = 'sent_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SentFolder {self.email_id}>'


class ImportantFolder(db.Model):
    __tablename__ = 'important_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ImportantFolder {self.email_id}>'


class ArchiveFolder(db.Model):
    __tablename__ = 'archive_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ArchiveFolder {self.email_id}>'


class DeletedFolder(db.Model):
    __tablename__ = 'deleted_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DeletedFolder {self.email_id}>'


class SpamFolder(db.Model):
    __tablename__ = 'spam_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SpamFolder {self.email_id}>'


class Note(db.Model):
    __tablename__ = 'notes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Note {self.title}>'


class SecurityLog(db.Model):
    __tablename__ = 'security_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    
    def __repr__(self):
        return f'<SecurityLog {self.action} at {self.timestamp}>'


class VirusScanLog(db.Model):
    __tablename__ = 'virus_scan_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    scan_result = db.Column(db.String(50), nullable=False)  # CLEAN, INFECTED, ERROR
    virus_name = db.Column(db.String(100))
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    scanned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def __repr__(self):
        return f'<VirusScanLog {self.filename} - {self.scan_result}>'


# ==================== NEW UNIQUE FEATURES ====================

class Task(db.Model):
    """Email to Task Converter - Convert emails into actionable tasks"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    priority = db.Column(db.String(10), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    due_date = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # AI-suggested fields
    ai_suggested_priority = db.Column(db.Boolean, default=False)
    ai_suggested_due_date = db.Column(db.Boolean, default=False)
    estimated_minutes = db.Column(db.Integer)  # AI-estimated time to complete
    
    # Subtasks
    subtasks = db.relationship('SubTask', backref='task', lazy='dynamic')
    
    def __repr__(self):
        return f'<Task {self.title}>'


class SubTask(db.Model):
    """Subtasks for tasks"""
    __tablename__ = 'subtasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SubTask {self.title}>'


class VaultItem(db.Model):
    """Secure Vault - Extra encrypted storage for sensitive emails and data"""
    __tablename__ = 'vault_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Encrypted content
    item_type = db.Column(db.String(20), default='note')  # note, email, password, file
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    encryption_key_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime)
    access_count = db.Column(db.Integer, default=0)
    auto_delete_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<VaultItem {self.title}>'


class EmailAnalytics(db.Model):
    """Email Analytics - Track email patterns and productivity"""
    __tablename__ = 'email_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    
    # Daily stats
    emails_sent = db.Column(db.Integer, default=0)
    emails_received = db.Column(db.Integer, default=0)
    emails_read = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float)  # in minutes
    total_read_time = db.Column(db.Integer, default=0)  # in seconds
    
    # Productivity metrics
    productivity_score = db.Column(db.Float, default=0.0)  # 0-100
    focus_time = db.Column(db.Integer, default=0)  # minutes in focus mode
    peak_productivity_hour = db.Column(db.Integer)
    
    # Communication patterns
    top_recipients = db.Column(db.Text)  # JSON array
    top_senders = db.Column(db.Text)  # JSON array
    avg_email_length = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailAnalytics {self.date}>'


class ScheduledEmail(db.Model):
    """Email Scheduler - Schedule emails to be sent later"""
    __tablename__ = 'scheduled_emails'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime)
    is_sent = db.Column(db.Boolean, default=False)
    is_cancelled = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(200))
    attachment_filename = db.Column(db.String(100))
    
    # Smart scheduling
    is_smart_scheduled = db.Column(db.Boolean, default=False)
    optimal_time_score = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScheduledEmail {self.subject}>'


class MoodLog(db.Model):
    """Mood Tracking - Track emotional tone of communications"""
    __tablename__ = 'mood_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Daily mood metrics
    avg_incoming_mood = db.Column(db.Float)  # -1 to 1
    avg_outgoing_mood = db.Column(db.Float)  # -1 to 1
    positive_count = db.Column(db.Integer, default=0)
    negative_count = db.Column(db.Integer, default=0)
    neutral_count = db.Column(db.Integer, default=0)
    
    # Insights
    mood_trend = db.Column(db.String(10))  # improving, declining, stable
    stress_indicators = db.Column(db.Text)  # JSON
    recommendations = db.Column(db.Text)  # JSON
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MoodLog {self.date}>'


class FocusSession(db.Model):
    """Focus Mode - Distraction-free email management sessions"""
    __tablename__ = 'focus_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    
    # Session stats
    emails_processed = db.Column(db.Integer, default=0)
    emails_composed = db.Column(db.Integer, default=0)
    tasks_completed = db.Column(db.Integer, default=0)
    
    # Settings used
    blocked_notifications = db.Column(db.Boolean, default=True)
    allowed_contacts = db.Column(db.Text)  # JSON array of allowed contacts
    
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<FocusSession {self.started_at}>'


class EmailTemplate(db.Model):
    """Smart Email Templates with Variables"""
    __tablename__ = 'email_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text)  # JSON array of variable names
    category = db.Column(db.String(50))  # business, personal, follow-up, etc.
    use_count = db.Column(db.Integer, default=0)
    is_shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailTemplate {self.name}>'


class EmailThread(db.Model):
    """Email Threading Visualization"""
    __tablename__ = 'email_threads'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    root_email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    participant_ids = db.Column(db.Text)  # JSON array of user IDs
    email_count = db.Column(db.Integer, default=1)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailThread {self.subject}>'


class SmartReply(db.Model):
    """AI-Generated Smart Replies"""
    __tablename__ = 'smart_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reply_options = db.Column(db.Text)  # JSON array of suggested replies
    selected_reply = db.Column(db.Integer)  # Index of selected reply
    was_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SmartReply for Email {self.email_id}>'


class EmailBookmark(db.Model):
    """Email Pinning/Bookmarking"""
    __tablename__ = 'email_bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    bookmark_type = db.Column(db.String(20), default='pin')  # pin, star, flag
    color = db.Column(db.String(10))  # for color-coding
    notes = db.Column(db.Text)  # user notes about this email
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailBookmark {self.email_id}>'


class FollowUpReminder(db.Model):
    """Follow-up Reminders"""
    __tablename__ = 'follow_up_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    reminder_at = db.Column(db.DateTime, nullable=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    is_dismissed = db.Column(db.Boolean, default=False)
    snooze_count = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<FollowUpReminder {self.reminder_at}>'


# ==================== CONTEXT MEMORY ACROSS THREADS ====================

class ContextMemory(db.Model):
    """Context Memory - Links related emails across threads"""
    __tablename__ = 'context_memories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    current_email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    related_email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    
    # Relevance scoring
    semantic_similarity_score = db.Column(db.Float, default=0.0)  # 0-1
    recency_score = db.Column(db.Float, default=0.0)  # 0-1
    participant_overlap_score = db.Column(db.Float, default=0.0)  # 0-1
    subject_alignment_score = db.Column(db.Float, default=0.0)  # 0-1
    action_item_score = db.Column(db.Float, default=0.0)  # 0-1
    overall_confidence = db.Column(db.Float, default=0.0)  # Weighted overall score
    
    # Confidence level
    confidence_level = db.Column(db.String(10), default='low')  # high, medium, low
    
    # Detection metadata
    detected_phrases = db.Column(db.Text)  # JSON array of detected context phrases
    detection_method = db.Column(db.String(20), default='auto')  # auto, manual
    
    # User feedback
    user_feedback = db.Column(db.String(10))  # relevant, not_relevant, null
    feedback_at = db.Column(db.DateTime)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='context_memories')
    current_email = db.relationship('Email', foreign_keys=[current_email_id])
    related_email = db.relationship('Email', foreign_keys=[related_email_id])
    
    def __repr__(self):
        return f'<ContextMemory {self.current_email_id} -> {self.related_email_id}>'


class ContextSummary(db.Model):
    """Generated summaries for related email threads"""
    __tablename__ = 'context_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    
    # Structured summary
    key_decisions = db.Column(db.Text)  # JSON array of decisions made
    pending_tasks = db.Column(db.Text)  # JSON array of pending tasks
    last_status = db.Column(db.Text)  # Last known status summary
    key_points = db.Column(db.Text)  # JSON array of key discussion points
    participants_summary = db.Column(db.Text)  # JSON summary of participants
    
    # Full summary text
    summary_text = db.Column(db.Text)  # Human-readable summary
    
    # Metadata
    thread_depth = db.Column(db.Integer, default=0)  # How deep in the thread
    email_count_in_thread = db.Column(db.Integer, default=1)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='context_summaries')
    email = db.relationship('Email', backref='context_summary')
    
    def __repr__(self):
        return f'<ContextSummary for Email {self.email_id}>'


class ContextPhrase(db.Model):
    """Context detection phrases for pattern matching"""
    __tablename__ = 'context_phrases'
    
    id = db.Column(db.Integer, primary_key=True)
    phrase = db.Column(db.String(200), nullable=False, unique=True)
    phrase_type = db.Column(db.String(20), default='reference')  # reference, followup, continuation
    weight = db.Column(db.Float, default=1.0)  # Importance weight
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ContextPhrase "{self.phrase}">'


class ContextFeedbackLog(db.Model):
    """Log of user feedback for improving context detection"""
    __tablename__ = 'context_feedback_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    context_memory_id = db.Column(db.Integer, db.ForeignKey('context_memories.id'))
    
    feedback_type = db.Column(db.String(20), nullable=False)  # relevant, not_relevant
    original_confidence = db.Column(db.Float)
    adjusted_confidence = db.Column(db.Float)
    
    # For learning
    features_snapshot = db.Column(db.Text)  # JSON of features at time of feedback
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='context_feedback_logs')
    context_memory = db.relationship('ContextMemory', backref='feedback_logs')
    
    def __repr__(self):
        return f'<ContextFeedbackLog {self.feedback_type}>'


# ==================== AI SENTIMENT ANALYSIS ====================

class SentimentAnalysis(db.Model):
    """Comprehensive sentiment analysis for all content types"""
    __tablename__ = 'sentiment_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Content references (polymorphic)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    
    # Core sentiment scores
    sentiment_score = db.Column(db.Float, default=0.0)  # -1 to 1
    sentiment_label = db.Column(db.String(20))  # positive, negative, neutral
    confidence = db.Column(db.Float, default=0.0)  # 0 to 1
    
    # Detailed scores
    positive_score = db.Column(db.Float, default=0.0)
    negative_score = db.Column(db.Float, default=0.0)
    neutral_score = db.Column(db.Float, default=0.0)
    
    # Emotion analysis (JSON)
    emotion_scores = db.Column(db.Text)  # JSON dict of emotion -> score
    emotion_percentages = db.Column(db.Text)  # JSON dict of emotion -> percentage
    dominant_emotions = db.Column(db.Text)  # JSON array of top emotions
    
    # Communication characteristics
    urgency_level = db.Column(db.String(20), default='normal')  # critical, high, medium, normal
    formality_level = db.Column(db.String(20), default='neutral')  # formal, semi-formal, neutral, informal
    
    # Text statistics (JSON)
    text_statistics = db.Column(db.Text)  # JSON with word count, sentence count, etc.
    
    # AI-generated insights (JSON)
    insights = db.Column(db.Text)  # JSON array of insight strings
    
    # Direction
    is_outgoing = db.Column(db.Boolean, default=True)  # True if sent by user, False if received
    
    # Timestamps
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='sentiment_analyses')
    email = db.relationship('Email', backref='sentiment_analysis_record')
    note = db.relationship('Note', backref='sentiment_analysis_record')
    task = db.relationship('Task', backref='sentiment_analysis_record')
    
    def __repr__(self):
        return f'<SentimentAnalysis {self.sentiment_label} ({self.sentiment_score})>'


class MoodInsight(db.Model):
    """AI-generated mood insights and recommendations"""
    __tablename__ = 'mood_insights'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Insight details
    insight_type = db.Column(db.String(30), nullable=False)  # trend, pattern, recommendation, alert
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Severity/importance
    importance = db.Column(db.String(10), default='info')  # critical, warning, info, success
    
    # Related data
    related_date = db.Column(db.DateTime)
    sentiment_range_start = db.Column(db.Float)
    sentiment_range_end = db.Column(db.Float)
    
    # Associated emotions
    emotions_involved = db.Column(db.Text)  # JSON array
    
    # Actionable recommendations
    recommendations = db.Column(db.Text)  # JSON array of recommended actions
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    is_dismissed = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='mood_insights')
    
    def __repr__(self):
        return f'<MoodInsight {self.insight_type}: {self.title}>'


class CommunicationPattern(db.Model):
    """Detected patterns in user communications"""
    __tablename__ = 'communication_patterns'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Pattern identification
    pattern_type = db.Column(db.String(30), nullable=False)  # time_based, contact_based, topic_based, emotion_based
    pattern_name = db.Column(db.String(100), nullable=False)
    
    # Pattern data
    pattern_data = db.Column(db.Text)  # JSON with pattern-specific data
    
    # Frequency
    occurrence_count = db.Column(db.Integer, default=1)
    last_occurrence = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Associated sentiment
    avg_sentiment = db.Column(db.Float)
    dominant_emotions = db.Column(db.Text)  # JSON array
    
    # Pattern strength (0-1)
    strength = db.Column(db.Float, default=0.5)
    
    # Timestamps
    first_detected = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='communication_patterns')
    
    def __repr__(self):
        return f'<CommunicationPattern {self.pattern_type}: {self.pattern_name}>'


# ==================== CALENDAR & EVENTS ====================

class CalendarEvent(db.Model):
    """Calendar Events and Meetings"""
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Event details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(300))
    event_type = db.Column(db.String(20), default='event')  # event, meeting, reminder, task
    
    # Timing
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    is_all_day = db.Column(db.Boolean, default=False)
    timezone = db.Column(db.String(50), default='UTC')
    
    # Recurrence
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(20))  # daily, weekly, monthly, yearly
    recurrence_end = db.Column(db.DateTime)
    parent_event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'))
    
    # Meeting specific
    is_meeting = db.Column(db.Boolean, default=False)
    meeting_link = db.Column(db.String(500))  # Zoom, Teams, Meet link
    meeting_platform = db.Column(db.String(20))  # zoom, teams, meet, other
    attendee_ids = db.Column(db.Text)  # JSON array of user IDs
    max_attendees = db.Column(db.Integer)
    
    # Reminder settings
    reminder_one_day = db.Column(db.Boolean, default=True)  # Reminder 1 day before
    reminder_one_hour = db.Column(db.Boolean, default=True)  # Reminder 1 hour before
    reminder_custom = db.Column(db.Integer)  # Custom reminder in minutes before
    reminder_one_day_sent = db.Column(db.Boolean, default=False)
    reminder_one_hour_sent = db.Column(db.Boolean, default=False)
    reminder_custom_sent = db.Column(db.Boolean, default=False)
    
    # Status
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, cancelled
    color = db.Column(db.String(10), default='#00d4ff')  # Event color
    
    # Linking
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    reminder_id = db.Column(db.Integer, db.ForeignKey('follow_up_reminders.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='calendar_events')
    task = db.relationship('Task', backref='calendar_event')
    email = db.relationship('Email', backref='calendar_event')
    reminder = db.relationship('FollowUpReminder', backref='calendar_event')
    parent_event = db.relationship('CalendarEvent', remote_side=[id], backref='child_events')
    
    def __repr__(self):
        return f'<CalendarEvent {self.title}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'location': self.location,
            'event_type': self.event_type,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_all_day': self.is_all_day,
            'is_meeting': self.is_meeting,
            'meeting_link': self.meeting_link,
            'meeting_platform': self.meeting_platform,
            'status': self.status,
            'color': self.color,
            'is_recurring': self.is_recurring
        }


class EventAttendee(db.Model):
    """Event attendees for meetings"""
    __tablename__ = 'event_attendees'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(120))  # For external attendees
    
    # Status
    response_status = db.Column(db.String(20), default='pending')  # pending, accepted, declined, tentative
    responded_at = db.Column(db.DateTime)
    
    # Timestamps
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    event = db.relationship('CalendarEvent', backref='attendees_list')
    user = db.relationship('User', backref='event_invitations')
    
    def __repr__(self):
        return f'<EventAttendee {self.email or self.user_id}>'


class EventNotification(db.Model):
    """Track event notifications sent to users"""
    __tablename__ = 'event_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=False)
    
    # Notification details
    notification_type = db.Column(db.String(20), nullable=False)  # one_day, one_hour, custom, schedule_popup
    scheduled_time = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime)
    
    # Status
    is_sent = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    # Content
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='event_notifications')
    event = db.relationship('CalendarEvent', backref='notifications')
    
    def __repr__(self):
        return f'<EventNotification {self.notification_type} for Event {self.event_id}>'
