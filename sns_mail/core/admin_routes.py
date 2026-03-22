from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from sqlalchemy import or_
from ..database.models import User, Email, Draft, SentFolder, ImportantFolder, ArchiveFolder, DeletedFolder, SpamFolder, Note, SecurityLog, VirusScanLog
from ..security.engine import SecurityEngine
from .. import db, limiter
from ..utils.validators import validate_email_domain, validate_password_strength, allowed_file
from ..utils.helpers import save_file, log_security_event

admin = Blueprint('admin', __name__)

@admin.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get statistics
    total_users = User.query.count()
    active_users = User.query.filter(User.last_login > datetime.utcnow() - timedelta(days=30)).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    total_emails = Email.query.count()
    spam_emails = Email.query.filter_by(is_spam=True).count()
    virus_scans = VirusScanLog.query.count()
    
    # Get recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_emails = Email.query.order_by(Email.sent_at.desc()).limit(10).all()
    recent_security_logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).limit(20).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         banned_users=banned_users,
                         total_emails=total_emails,
                         spam_emails=spam_emails,
                         virus_scans=virus_scans,
                         recent_users=recent_users,
                         recent_emails=recent_emails,
                         recent_security_logs=recent_security_logs)

@admin.route('/users')
@login_required
def users():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', users=users)

@admin.route('/user/<int:user_id>')
@login_required
def view_user(user_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    recent_sent = Email.query.filter_by(sender_id=user.id).order_by(Email.sent_at.desc()).limit(5).all()
    return render_template('admin/view_user.html', user=user, recent_sent=recent_sent)

@admin.route('/user/<int:user_id>/ban', methods=['POST'])
@login_required
def ban_user(user_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    reason = request.form.get('reason', 'Violation of terms of service')
    
    user.ban_user(reason)
    log_security_event(current_user.id, 'USER_BANNED', request.remote_addr,
                     f"User {user.username} banned by {current_user.username}. Reason: {reason}")
    
    flash(f'User {user.username} has been banned.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/user/<int:user_id>/unban', methods=['POST'])
@login_required
def unban_user(user_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.is_banned:
        flash('User is not banned.', 'info')
        return redirect(url_for('admin.users'))
    
    user.unban_user()
    log_security_event(current_user.id, 'USER_UNBANNED', request.remote_addr,
                     f"User {user.username} unbanned by {current_user.username}")
    
    flash(f'User {user.username} has been unbanned.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/user/<int:user_id>/promote-admin', methods=['POST'])
@login_required
def promote_admin(user_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('User is already an admin.', 'info')
        return redirect(url_for('admin.users'))
    
    user.is_admin = True
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_PROMOTED_ADMIN', request.remote_addr,
                     f"User {user.username} promoted to admin by {current_user.username}")
    
    flash(f'User {user.username} has been promoted to admin.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/user/<int:user_id>/demote-admin', methods=['POST'])
@login_required
def demote_admin(user_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.is_admin:
        flash('User is not an admin.', 'info')
        return redirect(url_for('admin.users'))
    
    if user.id == current_user.id:
        flash('You cannot demote yourself.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_admin = False
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_DEMOTED_ADMIN', request.remote_addr,
                     f"User {user.username} demoted from admin by {current_user.username}")
    
    flash(f'User {user.username} has been demoted from admin.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/user/<int:user_id>/promote-server-admin', methods=['POST'])
@login_required
def promote_server_admin(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can promote server admins.', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    
    if user.is_server_admin:
        flash('User is already a server admin.', 'info')
        return redirect(url_for('admin.users'))
    
    user.is_server_admin = True
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_PROMOTED_SERVER_ADMIN', request.remote_addr,
                     f"User {user.username} promoted to server admin by {current_user.username}")
    
    flash(f'User {user.username} has been promoted to server admin.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/user/<int:user_id>/demote-server-admin', methods=['POST'])
@login_required
def demote_server_admin(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can demote server admins.', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.is_server_admin:
        flash('User is not a server admin.', 'info')
        return redirect(url_for('admin.users'))
    
    if user.id == current_user.id:
        flash('You cannot demote yourself.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_server_admin = False
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_DEMOTED_SERVER_ADMIN', request.remote_addr,
                     f"User {user.username} demoted from server admin by {current_user.username}")
    
    flash(f'User {user.username} has been demoted from server admin.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/user/<int:user_id>/verify', methods=['POST'])
@login_required
def verify_user(user_id):
    """Assign verified blue tick badge to user"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.is_verified:
        flash('User is already verified.', 'info')
        return redirect(url_for('admin.users'))
    
    user.is_verified = True
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_VERIFIED', request.remote_addr,
                     f"User {user.username} verified by {current_user.username}")
    
    flash(f'User {user.username} has been verified with a blue tick badge.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/user/<int:user_id>/unverify', methods=['POST'])
@login_required
def unverify_user(user_id):
    """Remove verified blue tick badge from user"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.is_verified:
        flash('User is not verified.', 'info')
        return redirect(url_for('admin.users'))
    
    user.is_verified = False
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_UNVERIFIED', request.remote_addr,
                     f"User {user.username} unverified by {current_user.username}")
    
    flash(f'User {user.username} has been unverified.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/emails')
@login_required
def emails():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    emails = Email.query.order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/emails.html', emails=emails)

@admin.route('/email/<int:email_id>/delete', methods=['POST'])
@login_required
def delete_email_admin(email_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    
    # Remove from all folders
    ArchiveFolder.query.filter_by(email_id=email_id).delete()
    DeletedFolder.query.filter_by(email_id=email_id).delete()
    ImportantFolder.query.filter_by(email_id=email_id).delete()
    SpamFolder.query.filter_by(email_id=email_id).delete()
    SentFolder.query.filter_by(email_id=email_id).delete()
    
    # Remove attachment if exists
    if email.attachment_path and os.path.exists(email.attachment_path):
        os.remove(email.attachment_path)
    
    db.session.delete(email)
    db.session.commit()
    
    log_security_event(current_user.id, 'EMAIL_DELETED_ADMIN', request.remote_addr,
                     f"Email {email_id} deleted by admin {current_user.username}")
    
    flash('Email deleted successfully.', 'success')
    return redirect(url_for('admin.emails'))

@admin.route('/email/<int:email_id>/mark-spam', methods=['POST'])
@login_required
def mark_spam_admin(email_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    
    if not email.is_spam:
        email.is_spam = True
        db.session.commit()
        
        # Add to spam folder
        if not SpamFolder.query.filter_by(email_id=email_id, user_id=email.recipient_id).first():
            spam_folder = SpamFolder(email_id=email_id, user_id=email.recipient_id)
            db.session.add(spam_folder)
            db.session.commit()
        
        log_security_event(current_user.id, 'EMAIL_MARKED_SPAM_ADMIN', request.remote_addr,
                         f"Email {email_id} marked as spam by admin {current_user.username}")
        
        flash('Email marked as spam.', 'success')
    
    return redirect(url_for('admin.emails'))

@admin.route('/email/<int:email_id>/unmark-spam', methods=['POST'])
@login_required
def unmark_spam_admin(email_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    
    if email.is_spam:
        email.is_spam = False
        db.session.commit()
        
        # Remove from spam folder
        SpamFolder.query.filter_by(email_id=email_id, user_id=email.recipient_id).delete()
        db.session.commit()
        
        log_security_event(current_user.id, 'EMAIL_UNMARKED_SPAM_ADMIN', request.remote_addr,
                         f"Email {email_id} unmarked as spam by admin {current_user.username}")
        
        flash('Email unmarked as spam.', 'success')
    
    return redirect(url_for('admin.emails'))

@admin.route('/security-logs')
@login_required
def security_logs():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=50)
    return render_template('admin/security_logs.html', logs=logs)

@admin.route('/virus-scans')
@login_required
def virus_scans():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    scans = VirusScanLog.query.order_by(VirusScanLog.scanned_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/virus_scans.html', scans=scans)

@admin.route('/virus-scans/<int:scan_id>/delete', methods=['POST'])
@login_required
def delete_virus_scan(scan_id):
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    scan = VirusScanLog.query.get_or_404(scan_id)
    
    # Remove the file if it exists
    if scan.file_path and os.path.exists(scan.file_path):
        os.remove(scan.file_path)
    
    db.session.delete(scan)
    db.session.commit()
    
    log_security_event(current_user.id, 'VIRUS_SCAN_DELETED', request.remote_addr,
                     f"Virus scan {scan_id} deleted by admin {current_user.username}")
    
    flash('Virus scan record deleted.', 'success')
    return redirect(url_for('admin.virus_scans'))

@admin.route('/system-stats')
@login_required
def system_stats():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can view system stats.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get system statistics
    total_users = User.query.count()
    active_users = User.query.filter(User.last_login > datetime.utcnow() - timedelta(days=7)).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    server_admin_users = User.query.filter_by(is_server_admin=True).count()
    
    total_emails = Email.query.count()
    emails_today = Email.query.filter(Email.sent_at > datetime.utcnow() - timedelta(days=1)).count()
    emails_this_month = Email.query.filter(Email.sent_at > datetime.utcnow() - timedelta(days=30)).count()
    
    spam_emails = Email.query.filter_by(is_spam=True).count()
    important_emails = Email.query.filter_by(is_important=True).count()
    deleted_emails = DeletedFolder.query.count()
    archived_emails = ArchiveFolder.query.count()
    
    total_notes = Note.query.count()
    total_drafts = Draft.query.count()
    
    virus_scans = VirusScanLog.query.count()
    infected_files = VirusScanLog.query.filter_by(scan_result='INFECTED').count()
    
    # Get recent activity
    recent_logins = SecurityLog.query.filter_by(action='LOGIN_SUCCESS').order_by(SecurityLog.timestamp.desc()).limit(10).all()
    recent_registrations = SecurityLog.query.filter_by(action='ACCOUNT_CREATED').order_by(SecurityLog.timestamp.desc()).limit(10).all()
    
    return render_template('admin/system_stats.html',
                         total_users=total_users,
                         active_users=active_users,
                         banned_users=banned_users,
                         admin_users=admin_users,
                         server_admin_users=server_admin_users,
                         total_emails=total_emails,
                         emails_today=emails_today,
                         emails_this_month=emails_this_month,
                         spam_emails=spam_emails,
                         important_emails=important_emails,
                         deleted_emails=deleted_emails,
                         archived_emails=archived_emails,
                         total_notes=total_notes,
                         total_drafts=total_drafts,
                         virus_scans=virus_scans,
                         infected_files=infected_files,
                         recent_logins=recent_logins,
                         recent_registrations=recent_registrations)

@admin.route('/system-settings')
@login_required
def system_settings():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can modify system settings.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('admin/system_settings.html')

@admin.route('/system-settings/update', methods=['POST'])
@login_required
def update_system_settings():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can modify system settings.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would update system configuration
    # For now, just log the attempt
    log_security_event(current_user.id, 'SYSTEM_SETTINGS_UPDATED', request.remote_addr,
                     f"System settings updated by {current_user.username}")
    
    flash('System settings updated successfully.', 'success')
    return redirect(url_for('admin.system_settings'))

@admin.route('/maintenance')
@login_required
def maintenance():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can perform maintenance.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('admin/maintenance.html')

@admin.route('/maintenance/clear-logs', methods=['POST'])
@login_required
def clear_logs():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can perform maintenance.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Clear old security logs (keep last 30 days)
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    SecurityLog.query.filter(SecurityLog.timestamp < cutoff_date).delete()
    db.session.commit()
    
    log_security_event(current_user.id, 'LOGS_CLEARED', request.remote_addr,
                     f"Old security logs cleared by {current_user.username}")
    
    flash('Old security logs cleared successfully.', 'success')
    return redirect(url_for('admin.maintenance'))

@admin.route('/maintenance/scan-viruses', methods=['POST'])
@login_required
def scan_viruses():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can perform maintenance.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would trigger a full virus scan of all attachments
    # For now, just log the attempt
    log_security_event(current_user.id, 'VIRUS_SCAN_TRIGGERED', request.remote_addr,
                     f"Virus scan triggered by {current_user.username}")
    
    flash('Virus scan initiated successfully.', 'success')
    return redirect(url_for('admin.maintenance'))

@admin.route('/reports')
@login_required
def reports():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('admin/reports.html')

@admin.route('/reports/user-activity')
@login_required
def user_activity_report():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Generate user activity report
    users = User.query.order_by(User.last_login.desc()).all()
    return render_template('admin/user_activity_report.html', users=users)

@admin.route('/reports/email-activity')
@login_required
def email_activity_report():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Generate email activity report
    emails = Email.query.order_by(Email.sent_at.desc()).limit(100).all()
    return render_template('admin/email_activity_report.html', emails=emails)

@admin.route('/reports/security-incidents')
@login_required
def security_incidents_report():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Generate security incidents report
    incidents = SecurityLog.query.filter(
        SecurityLog.action.in_(['LOGIN_FAILED_PASSWORD', 'LOGIN_FAILED_2FA', 'VIRUS_DETECTED', 'USER_BANNED'])
    ).order_by(SecurityLog.timestamp.desc()).limit(100).all()
    
    return render_template('admin/security_incidents_report.html', incidents=incidents)


# ==================== CONTEXT MEMORY MANAGEMENT ====================

from ..database.models import ContextMemory, ContextSummary, ContextPhrase, ContextFeedbackLog

@admin.route('/context-memory')
@login_required
def context_memory():
    """Context Memory Management Page"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get statistics
    total_memories = ContextMemory.query.filter_by(is_active=True).count()
    high_confidence = ContextMemory.query.filter_by(confidence_level='high', is_active=True).count()
    medium_confidence = ContextMemory.query.filter_by(confidence_level='medium', is_active=True).count()
    low_confidence = ContextMemory.query.filter_by(confidence_level='low', is_active=True).count()
    total_phrases = ContextPhrase.query.filter_by(is_active=True).count()
    total_summaries = ContextSummary.query.count()
    total_feedback = ContextFeedbackLog.query.count()
    relevant_feedback = ContextFeedbackLog.query.filter_by(feedback_type='relevant').count()
    not_relevant_feedback = ContextFeedbackLog.query.filter_by(feedback_type='not_relevant').count()
    
    # Count active threads (unique related_email_ids)
    from sqlalchemy import func
    active_threads = db.session.query(func.count(func.distinct(ContextMemory.related_email_id))).filter(
        ContextMemory.is_active == True
    ).scalar() or 0
    
    stats = {
        'total_memories': total_memories,
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'low_confidence': low_confidence,
        'total_phrases': total_phrases,
        'total_summaries': total_summaries,
        'total_feedback': total_feedback,
        'relevant_feedback': relevant_feedback,
        'not_relevant_feedback': not_relevant_feedback,
        'active_threads': active_threads
    }
    
    # Get phrases
    phrases = ContextPhrase.query.filter_by(is_active=True).order_by(ContextPhrase.phrase_type, ContextPhrase.phrase).all()
    
    # Get recent feedback logs
    feedback_logs = ContextFeedbackLog.query.order_by(ContextFeedbackLog.created_at.desc()).limit(50).all()
    
    # Get recent memories
    recent_memories = ContextMemory.query.filter_by(is_active=True).order_by(ContextMemory.created_at.desc()).limit(20).all()
    
    return render_template('admin/context_memory.html',
                         stats=stats,
                         phrases=phrases,
                         feedback_logs=feedback_logs,
                         recent_memories=recent_memories)


@admin.route('/context-memory/analyze', methods=['POST'])
@login_required
def analyze_emails_context():
    """Analyze all emails for context memory"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    try:
        from ..utils.context_memory_engine import context_engine
        
        # Get ALL emails in the system
        all_emails = Email.query.filter_by(is_deleted=False).all()
        new_links = 0
        
        for email in all_emails:
            try:
                # Analyze for both sender and recipient
                if email.sender_id:
                    result = context_engine.analyze_email_sync(email.id, email.sender_id)
                    if result and result.get('related_count', 0) > 0:
                        new_links += result.get('related_count', 0)
                
                if email.recipient_id and email.recipient_id != email.sender_id:
                    result = context_engine.analyze_email_sync(email.id, email.recipient_id)
                    if result and result.get('related_count', 0) > 0:
                        new_links += result.get('related_count', 0)
            except Exception:
                continue
        
        flash(f'Analysis complete! {new_links} new context links found from {len(all_emails)} emails analyzed.', 'success')
    except Exception as e:
        flash(f'Error during analysis: {str(e)}', 'danger')
    
    return redirect(url_for('admin.context_memory'))


@admin.route('/context-memory/phrase/add', methods=['POST'])
@login_required
def add_context_phrase():
    """Add a new context detection phrase"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    phrase = request.form.get('phrase', '').lower().strip()
    phrase_type = request.form.get('phrase_type', 'reference')
    weight = float(request.form.get('weight', 1.0))
    
    if not phrase:
        flash('Phrase is required.', 'danger')
        return redirect(url_for('admin.context_memory'))
    
    # Check if already exists
    existing = ContextPhrase.query.filter_by(phrase=phrase).first()
    if existing:
        flash('Phrase already exists.', 'warning')
        return redirect(url_for('admin.context_memory'))
    
    new_phrase = ContextPhrase(
        phrase=phrase,
        phrase_type=phrase_type,
        weight=weight,
        is_active=True
    )
    db.session.add(new_phrase)
    db.session.commit()
    
    flash(f'Phrase "{phrase}" added successfully.', 'success')
    return redirect(url_for('admin.context_memory'))


@admin.route('/context-memory/phrase/<int:phrase_id>/delete', methods=['POST'])
@login_required
def delete_context_phrase(phrase_id):
    """Delete a context detection phrase"""
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    phrase = ContextPhrase.query.get_or_404(phrase_id)
    phrase.is_active = False
    db.session.commit()
    
    flash(f'Phrase "{phrase.phrase}" deactivated.', 'success')
    return redirect(url_for('admin.context_memory'))
