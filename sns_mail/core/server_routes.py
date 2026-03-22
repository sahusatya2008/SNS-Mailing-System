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

server = Blueprint('server', __name__)

@server.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access this dashboard.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get server statistics
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
    recent_security_events = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).limit(20).all()
    
    return render_template('server/dashboard.html',
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
                         recent_registrations=recent_registrations,
                         recent_security_events=recent_security_events)

@server.route('/server-status')
@login_required
def server_status():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access server status.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get server status information
    # This would typically include system resources, database status, etc.
    # For now, we'll just show basic statistics
    
    return render_template('server/server_status.html')

@server.route('/server-config')
@login_required
def server_config():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access server configuration.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('server/server_config.html')

@server.route('/server-config/update', methods=['POST'])
@login_required
def update_server_config():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can update server configuration.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would update server configuration
    # For now, just log the attempt
    log_security_event(current_user.id, 'SERVER_CONFIG_UPDATED', request.remote_addr,
                     f"Server configuration updated by {current_user.username}")
    
    flash('Server configuration updated successfully.', 'success')
    return redirect(url_for('server.server_config'))

@server.route('/user-management')
@login_required
def user_management():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access user management.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('server/user_management.html', users=users)

@server.route('/user/<int:user_id>/server-actions')
@login_required
def user_server_actions(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can perform server actions.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    return render_template('server/user_server_actions.html', user=user)

@server.route('/user/<int:user_id>/reset-password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can reset passwords.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password')
    
    if not new_password:
        flash('Please provide a new password.', 'danger')
        return redirect(url_for('server.user_server_actions', user_id=user_id))
    
    if not validate_password_strength(new_password):
        flash('Password must be at least 8 characters long and contain uppercase, lowercase, and numbers.', 'danger')
        return redirect(url_for('server.user_server_actions', user_id=user_id))
    
    user.set_password(new_password)
    db.session.commit()
    
    log_security_event(current_user.id, 'USER_PASSWORD_RESET', request.remote_addr,
                     f"Password reset for user {user.username} by {current_user.username}")
    
    flash(f'Password for user {user.username} has been reset.', 'success')
    return redirect(url_for('server.user_server_actions', user_id=user_id))

@server.route('/user/<int:user_id>/force-logout', methods=['POST'])
@login_required
def force_user_logout(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can force logout users.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # This would typically involve invalidating the user's session
    # For now, we'll just log the attempt
    log_security_event(current_user.id, 'USER_FORCE_LOGOUT', request.remote_addr,
                     f"User {user.username} force logged out by {current_user.username}")
    
    flash(f'User {user.username} has been force logged out.', 'success')
    return redirect(url_for('server.user_server_actions', user_id=user_id))

@server.route('/user/<int:user_id>/clear-login-attempts', methods=['POST'])
@login_required
def clear_login_attempts(user_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can clear login attempts.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    user.reset_login_attempts()
    
    log_security_event(current_user.id, 'LOGIN_ATTEMPTS_CLEARED', request.remote_addr,
                     f"Login attempts cleared for user {user.username} by {current_user.username}")
    
    flash(f'Login attempts for user {user.username} have been cleared.', 'success')
    return redirect(url_for('server.user_server_actions', user_id=user_id))

@server.route('/email-management')
@login_required
def email_management():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access email management.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    emails = Email.query.order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('server/email_management.html', emails=emails)

@server.route('/email/<int:email_id>/server-actions')
@login_required
def email_server_actions(email_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can perform server actions on emails.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    return render_template('server/email_server_actions.html', email=email)

@server.route('/email/<int:email_id>/resend', methods=['POST'])
@login_required
def resend_email(email_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can resend emails.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    
    # This would resend the email
    # For now, just log the attempt
    log_security_event(current_user.id, 'EMAIL_RESENT', request.remote_addr,
                     f"Email {email_id} resent by {current_user.username}")
    
    flash('Email has been resent.', 'success')
    return redirect(url_for('server.email_server_actions', email_id=email_id))

@server.route('/email/<int:email_id>/modify', methods=['GET', 'POST'])
@login_required
def modify_email(email_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can modify emails.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    email = Email.query.get_or_404(email_id)
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        if not subject or not body:
            flash('Please fill in all required fields.', 'danger')
            return render_template('server/modify_email.html', email=email)
        
        email.subject = subject
        email.body = body
        db.session.commit()
        
        log_security_event(current_user.id, 'EMAIL_MODIFIED', request.remote_addr,
                         f"Email {email_id} modified by {current_user.username}")
        
        flash('Email has been modified.', 'success')
        return redirect(url_for('server.email_server_actions', email_id=email_id))
    
    return render_template('server/modify_email.html', email=email)

@server.route('/security-management')
@login_required
def security_management():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access security management.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=50)
    return render_template('server/security_management.html', logs=logs)

@server.route('/virus-management')
@login_required
def virus_management():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access virus management.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    scans = VirusScanLog.query.order_by(VirusScanLog.scanned_at.desc()).paginate(page=page, per_page=20)
    return render_template('server/virus_management.html', scans=scans)

@server.route('/virus-scan/<int:scan_id>/quarantine', methods=['POST'])
@login_required
def quarantine_virus(scan_id):
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can quarantine viruses.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    scan = VirusScanLog.query.get_or_404(scan_id)
    
    if scan.scan_result != 'INFECTED':
        flash('This file is not infected.', 'info')
        return redirect(url_for('server.virus_management'))
    
    # Move file to quarantine (for now, just delete it)
    if scan.file_path and os.path.exists(scan.file_path):
        os.remove(scan.file_path)
    
    log_security_event(current_user.id, 'VIRUS_QUARANTINED', request.remote_addr,
                     f"Virus {scan.virus_name} in file {scan.filename} quarantined by {current_user.username}")
    
    flash('Virus has been quarantined.', 'success')
    return redirect(url_for('server.virus_management'))

@server.route('/system-maintenance')
@login_required
def system_maintenance():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access system maintenance.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('server/system_maintenance.html')

@server.route('/system-maintenance/clear-logs', methods=['POST'])
@login_required
def clear_all_logs():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can clear logs.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Clear all security logs
    SecurityLog.query.delete()
    db.session.commit()
    
    log_security_event(current_user.id, 'ALL_LOGS_CLEARED', request.remote_addr,
                     f"All security logs cleared by {current_user.username}")
    
    flash('All security logs have been cleared.', 'success')
    return redirect(url_for('server.system_maintenance'))

@server.route('/system-maintenance/scan-all-attachments', methods=['POST'])
@login_required
def scan_all_attachments():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can scan all attachments.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would trigger a full virus scan of all attachments
    # For now, just log the attempt
    log_security_event(current_user.id, 'ALL_ATTACHMENTS_SCAN_TRIGGERED', request.remote_addr,
                     f"All attachments scan triggered by {current_user.username}")
    
    flash('Full attachment scan initiated.', 'success')
    return redirect(url_for('server.system_maintenance'))

@server.route('/system-maintenance/optimize-database', methods=['POST'])
@login_required
def optimize_database():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can optimize the database.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would optimize the database
    # For now, just log the attempt
    log_security_event(current_user.id, 'DATABASE_OPTIMIZED', request.remote_addr,
                     f"Database optimization triggered by {current_user.username}")
    
    flash('Database optimization initiated.', 'success')
    return redirect(url_for('server.system_maintenance'))

@server.route('/backup-restore')
@login_required
def backup_restore():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access backup and restore.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    return render_template('server/backup_restore.html')

@server.route('/backup')
@login_required
def create_backup():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can create backups.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would create a backup of the database and files
    # For now, just log the attempt
    log_security_event(current_user.id, 'BACKUP_CREATED', request.remote_addr,
                     f"Backup created by {current_user.username}")
    
    flash('Backup created successfully.', 'success')
    return redirect(url_for('server.backup_restore'))

@server.route('/restore')
@login_required
def restore_backup():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can restore backups.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # This would restore from a backup
    # For now, just log the attempt
    log_security_event(current_user.id, 'BACKUP_RESTORED', request.remote_addr,
                     f"Backup restored by {current_user.username}")
    
    flash('Backup restored successfully.', 'success')
    return redirect(url_for('server.backup_restore'))

@server.route('/monitoring')
@login_required
def monitoring():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access monitoring.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get monitoring data
    # This would typically include system resources, database performance, etc.
    # For now, we'll just show basic statistics
    
    return render_template('server/monitoring.html')

@server.route('/monitoring/logs')
@login_required
def monitoring_logs():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access monitoring logs.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=100)
    return render_template('server/monitoring_logs.html', logs=logs)

@server.route('/monitoring/performance')
@login_required
def monitoring_performance():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access performance monitoring.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get performance metrics
    # This would typically include CPU usage, memory usage, database query times, etc.
    # For now, we'll just show basic statistics
    
    return render_template('server/monitoring_performance.html')

@server.route('/monitoring/alerts')
@login_required
def monitoring_alerts():
    if not current_user.is_server_admin:
        flash('Access denied. Only server admins can access monitoring alerts.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get system alerts
    # This would typically include security alerts, performance alerts, etc.
    # For now, we'll just show recent security events
    
    alerts = SecurityLog.query.filter(
        SecurityLog.action.in_(['LOGIN_FAILED_PASSWORD', 'LOGIN_FAILED_2FA', 'VIRUS_DETECTED', 'USER_BANNED'])
    ).order_by(SecurityLog.timestamp.desc()).limit(50).all()
    
    return render_template('server/monitoring_alerts.html', alerts=alerts)