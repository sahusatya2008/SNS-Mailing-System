from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from sqlalchemy import or_
from ..database.models import User, Email, Draft, SentFolder, ImportantFolder, ArchiveFolder, DeletedFolder, SpamFolder, Note, SecurityLog, VirusScanLog
from ..security.engine import SecurityEngine
from ..mail_engine.smtp_server import send_email
from .. import db, limiter
from ..utils.validators import validate_email_domain, validate_password_strength, allowed_file
from ..utils.helpers import save_file, log_security_event, scan_file_for_viruses
from ..core.qr_engine import QRScanner

api = Blueprint('api', __name__)

@api.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    """Get current user profile"""
    return jsonify({
        'id': current_user.id,
        'name': current_user.name,
        'username': current_user.username,
        'email': current_user.email,
        'is_admin': current_user.is_admin,
        'is_server_admin': current_user.is_server_admin,
        'is_2fa_enabled': current_user.is_2fa_enabled,
        'face_photo': current_user.face_photo,
        'eye_scan': current_user.eye_scan,
        'created_at': current_user.created_at.isoformat(),
        'last_login': current_user.last_login.isoformat() if current_user.last_login else None
    })

@api.route('/user/profile', methods=['PUT'])
@login_required
def update_user_profile():
    """Update current user profile"""
    data = request.get_json()
    
    if 'name' in data:
        current_user.name = data['name']
    
    if 'username' in data:
        # Check if username is already taken by another user
        existing_user = User.query.filter(User.username == data['username'], User.id != current_user.id).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400
        current_user.username = data['username']
    
    db.session.commit()
    log_security_event(current_user.id, 'PROFILE_UPDATED_API', request.remote_addr, 
                     f"Profile updated via API: {current_user.username}")
    
    return jsonify({'message': 'Profile updated successfully'})

@api.route('/user/avatar', methods=['POST'])
@login_required
def update_avatar_api():
    """Update user avatar via API"""
    if 'avatar' not in request.files:
        return jsonify({'error': 'No avatar file provided'}), 400
    
    avatar = request.files['avatar']
    
    if avatar and allowed_file(avatar.filename):
        # Remove old avatar if exists
        if current_user.face_photo and os.path.exists(current_user.face_photo):
            os.remove(current_user.face_photo)
        
        # Save new avatar
        avatar_path = save_file(avatar, 'avatars', current_user.username)
        current_user.face_photo = avatar_path
        db.session.commit()
        
        log_security_event(current_user.id, 'AVATAR_UPDATED_API', request.remote_addr, 
                         f"Avatar updated via API for user: {current_user.username}")
        
        return jsonify({'message': 'Avatar updated successfully', 'avatar_path': avatar_path})
    
    return jsonify({'error': 'Invalid file format'}), 400

@api.route('/user/eye-scan', methods=['POST'])
@login_required
def update_eye_scan_api():
    """Update user eye scan via API"""
    if 'eye_scan' not in request.files:
        return jsonify({'error': 'No eye scan file provided'}), 400
    
    eye_scan = request.files['eye_scan']
    
    if eye_scan and allowed_file(eye_scan.filename):
        # Remove old eye scan if exists
        if current_user.eye_scan and os.path.exists(current_user.eye_scan):
            os.remove(current_user.eye_scan)
        
        # Save new eye scan
        eye_scan_path = save_file(eye_scan, 'eye_scans', current_user.username)
        current_user.eye_scan = eye_scan_path
        db.session.commit()
        
        log_security_event(current_user.id, 'EYE_SCAN_UPDATED_API', request.remote_addr, 
                         f"Eye scan updated via API for user: {current_user.username}")
        
        return jsonify({'message': 'Eye scan updated successfully', 'eye_scan_path': eye_scan_path})
    
    return jsonify({'error': 'Invalid file format'}), 400

@api.route('/user/2fa/setup', methods=['GET'])
@login_required
def setup_2fa_api():
    """Get 2FA setup information"""
    if current_user.is_2fa_enabled:
        return jsonify({'error': '2FA is already enabled'}), 400
    
    return jsonify({
        'secret': current_user.totp_secret,
        'qr_code': current_user.get_qr_code(),
        'manual_entry_key': current_user.totp_secret
    })

@api.route('/user/2fa/enable', methods=['POST'])
@login_required
def enable_2fa_api():
    """Enable 2FA"""
    data = request.get_json()
    totp_code = data.get('totp_code')
    
    if not totp_code:
        return jsonify({'error': 'TOTP code is required'}), 400
    
    if current_user.verify_totp(totp_code):
        current_user.is_2fa_enabled = True
        db.session.commit()
        log_security_event(current_user.id, '2FA_ENABLED_API', request.remote_addr, 
                         f"2FA enabled via API for user: {current_user.username}")
        return jsonify({'message': '2FA enabled successfully'})
    else:
        return jsonify({'error': 'Invalid TOTP code'}), 400

@api.route('/user/2fa/disable', methods=['POST'])
@login_required
def disable_2fa_api():
    """Disable 2FA"""
    data = request.get_json()
    password = data.get('password')
    
    if not current_user.check_password(password):
        return jsonify({'error': 'Invalid password'}), 400
    
    current_user.is_2fa_enabled = False
    db.session.commit()
    log_security_event(current_user.id, '2FA_DISABLED_API', request.remote_addr, 
                     f"2FA disabled via API for user: {current_user.username}")
    return jsonify({'message': '2FA disabled successfully'})

@api.route('/emails', methods=['GET'])
@login_required
def get_emails_api():
    """Get user emails"""
    page = request.args.get('page', 1, type=int)
    folder = request.args.get('folder', 'inbox')
    
    if folder == 'inbox':
        emails = Email.query.filter_by(recipient_id=current_user.id, is_deleted=False, is_spam=False)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    elif folder == 'sent':
        emails = Email.query.filter_by(sender_id=current_user.id, is_deleted=False)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    elif folder == 'important':
        emails = Email.query.filter_by(recipient_id=current_user.id, is_important=True, is_deleted=False)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    elif folder == 'archive':
        emails = Email.query.join(ArchiveFolder).filter(ArchiveFolder.user_id == current_user.id)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    elif folder == 'deleted':
        emails = Email.query.join(DeletedFolder).filter(DeletedFolder.user_id == current_user.id)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    elif folder == 'spam':
        emails = Email.query.filter_by(recipient_id=current_user.id, is_spam=True, is_deleted=False)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    else:
        return jsonify({'error': 'Invalid folder'}), 400
    
    email_list = []
    for email in emails.items:
        email_list.append({
            'id': email.id,
            'subject': email.subject,
            'body': email.body,
            'sender': email.sender.email,
            'recipient': email.recipient.email,
            'sent_at': email.sent_at.isoformat(),
            'is_read': email.is_read,
            'is_important': email.is_important,
            'is_spam': email.is_spam,
            'attachment_filename': email.attachment_filename,
            'virus_detected': email.virus_detected
        })
    
    return jsonify({
        'emails': email_list,
        'total': emails.total,
        'pages': emails.pages,
        'current_page': emails.page
    })

@api.route('/email/<int:email_id>', methods=['GET'])
@login_required
def get_email_api(email_id):
    """Get specific email"""
    email = Email.query.get_or_404(email_id)
    
    # Check if user has access to this email
    if email.recipient_id != current_user.id and email.sender_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Mark as read if it's incoming
    if email.recipient_id == current_user.id and not email.is_read:
        email.mark_as_read()
    
    return jsonify({
        'id': email.id,
        'subject': email.subject,
        'body': email.body,
        'sender': email.sender.email,
        'recipient': email.recipient.email,
        'sent_at': email.sent_at.isoformat(),
        'read_at': email.read_at.isoformat() if email.read_at else None,
        'is_read': email.is_read,
        'is_important': email.is_important,
        'is_spam': email.is_spam,
        'attachment_filename': email.attachment_filename,
        'virus_detected': email.virus_detected
    })

@api.route('/email/<int:email_id>/mark-read', methods=['POST'])
@login_required
def mark_email_read_api(email_id):
    """Mark email as read"""
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    email.mark_as_read()
    return jsonify({'message': 'Email marked as read'})

@api.route('/email/<int:email_id>/mark-important', methods=['POST'])
@login_required
def mark_email_important_api(email_id):
    """Toggle email important status"""
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    email.toggle_important()
    return jsonify({'message': 'Email important status updated', 'is_important': email.is_important})

@api.route('/email/<int:email_id>/archive', methods=['POST'])
@login_required
def archive_email_api(email_id):
    """Archive email"""
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Add to archive folder
    if not ArchiveFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        archive_folder = ArchiveFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(archive_folder)
        db.session.commit()
    
    return jsonify({'message': 'Email archived successfully'})

@api.route('/email/<int:email_id>/delete', methods=['POST'])
@login_required
def delete_email_api(email_id):
    """Delete email"""
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Add to deleted folder
    if not DeletedFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        deleted_folder = DeletedFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(deleted_folder)
        db.session.commit()
    
    return jsonify({'message': 'Email moved to trash'})

@api.route('/email/<int:email_id>/spam', methods=['POST'])
@login_required
def mark_spam_api(email_id):
    """Mark email as spam"""
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    email.mark_as_spam()
    
    # Add to spam folder
    if not SpamFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        spam_folder = SpamFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(spam_folder)
        db.session.commit()
    
    return jsonify({'message': 'Email marked as spam'})

@api.route('/compose', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def compose_email_api():
    """Compose and send email via API"""
    data = request.get_json()
    
    recipient_email = data.get('recipient')
    subject = data.get('subject')
    body = data.get('body')
    
    if not recipient_email or not subject or not body:
        return jsonify({'error': 'Please fill in all required fields'}), 400
    
    # Check if recipient exists
    recipient = User.query.filter_by(email=recipient_email).first()
    if not recipient:
        return jsonify({'error': 'Recipient email not found'}), 400
    
    try:
        # Send email
        email = Email(
            subject=subject,
            body=body,
            sender_id=current_user.id,
            recipient_id=recipient.id
        )
        db.session.add(email)
        db.session.commit()
        
        # Add to sent folder
        sent_folder = SentFolder(email_id=email.id, user_id=current_user.id)
        db.session.add(sent_folder)
        db.session.commit()
        
        # Send via SMTP
        try:
            send_email(
                sender_email=current_user.email,
                recipient_email=recipient.email,
                subject=subject,
                body=body
            )
        except Exception as e:
            log_security_event(current_user.id, 'EMAIL_SEND_FAILED_API', request.remote_addr,
                             f"Failed to send email via API: {str(e)}")
        
        return jsonify({'message': 'Email sent successfully', 'email_id': email.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to send email'}), 500

@api.route('/drafts', methods=['GET'])
@login_required
def get_drafts_api():
    """Get user drafts"""
    drafts = Draft.query.filter_by(user_id=current_user.id).order_by(Draft.updated_at.desc()).all()
    
    draft_list = []
    for draft in drafts:
        draft_list.append({
            'id': draft.id,
            'subject': draft.subject,
            'body': draft.body,
            'recipient_email': draft.recipient_email,
            'created_at': draft.created_at.isoformat(),
            'updated_at': draft.updated_at.isoformat(),
            'attachment_filename': draft.attachment_filename
        })
    
    return jsonify({'drafts': draft_list})

@api.route('/draft/<int:draft_id>', methods=['GET'])
@login_required
def get_draft_api(draft_id):
    """Get specific draft"""
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': draft.id,
        'subject': draft.subject,
        'body': draft.body,
        'recipient_email': draft.recipient_email,
        'created_at': draft.created_at.isoformat(),
        'updated_at': draft.updated_at.isoformat(),
        'attachment_filename': draft.attachment_filename
    })

@api.route('/draft', methods=['POST'])
@login_required
def create_draft_api():
    """Create new draft"""
    data = request.get_json()
    
    subject = data.get('subject')
    body = data.get('body')
    recipient_email = data.get('recipient_email')
    
    if not subject or not body or not recipient_email:
        return jsonify({'error': 'Please fill in all required fields'}), 400
    
    try:
        draft = Draft(
            subject=subject,
            body=body,
            recipient_email=recipient_email,
            user_id=current_user.id
        )
        db.session.add(draft)
        db.session.commit()
        
        return jsonify({'message': 'Draft saved successfully', 'draft_id': draft.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save draft'}), 500

@api.route('/draft/<int:draft_id>', methods=['PUT'])
@login_required
def update_draft_api(draft_id):
    """Update existing draft"""
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    draft.subject = data.get('subject', draft.subject)
    draft.body = data.get('body', draft.body)
    draft.recipient_email = data.get('recipient_email', draft.recipient_email)
    draft.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'message': 'Draft updated successfully'})

@api.route('/draft/<int:draft_id>', methods=['DELETE'])
@login_required
def delete_draft_api(draft_id):
    """Delete draft"""
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Remove attachment if exists
    if draft.attachment_path and os.path.exists(draft.attachment_path):
        os.remove(draft.attachment_path)
    
    db.session.delete(draft)
    db.session.commit()
    
    return jsonify({'message': 'Draft deleted successfully'})

@api.route('/notes', methods=['GET'])
@login_required
def get_notes_api():
    """Get user notes"""
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    
    note_list = []
    for note in notes:
        note_list.append({
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat()
        })
    
    return jsonify({'notes': note_list})

@api.route('/note/<int:note_id>', methods=['GET'])
@login_required
def get_note_api(note_id):
    """Get specific note"""
    note = Note.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': note.id,
        'title': note.title,
        'content': note.content,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat()
    })

@api.route('/note', methods=['POST'])
@login_required
def create_note_api():
    """Create new note"""
    data = request.get_json()
    
    title = data.get('title')
    content = data.get('content')
    
    if not title or not content:
        return jsonify({'error': 'Please fill in all required fields'}), 400
    
    try:
        note = Note(title=title, content=content, user_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        
        return jsonify({'message': 'Note created successfully', 'note_id': note.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create note'}), 500

@api.route('/note/<int:note_id>', methods=['PUT'])
@login_required
def update_note_api(note_id):
    """Update existing note"""
    note = Note.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    note.title = data.get('title', note.title)
    note.content = data.get('content', note.content)
    note.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'message': 'Note updated successfully'})

@api.route('/note/<int:note_id>', methods=['DELETE'])
@login_required
def delete_note_api(note_id):
    """Delete note"""
    note = Note.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(note)
    db.session.commit()
    
    return jsonify({'message': 'Note deleted successfully'})

@api.route('/search', methods=['GET'])
@login_required
def search_api():
    """Search emails"""
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        emails = Email.query.filter_by(recipient_id=current_user.id, is_deleted=False)\
            .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    else:
        emails = Email.query.filter(
            Email.recipient_id == current_user.id,
            Email.is_deleted == False,
            or_(
                Email.subject.contains(query),
                Email.body.contains(query)
            )
        ).order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    
    email_list = []
    for email in emails.items:
        email_list.append({
            'id': email.id,
            'subject': email.subject,
            'body': email.body,
            'sender': email.sender.email,
            'recipient': email.recipient.email,
            'sent_at': email.sent_at.isoformat(),
            'is_read': email.is_read,
            'is_important': email.is_important,
            'is_spam': email.is_spam,
            'attachment_filename': email.attachment_filename,
            'virus_detected': email.virus_detected
        })
    
    return jsonify({
        'emails': email_list,
        'total': emails.total,
        'pages': emails.pages,
        'current_page': emails.page,
        'query': query
    })

@api.route('/qr-scan', methods=['POST'])
@login_required
def qr_scan_api():
    """Scan QR code"""
    data = request.get_json()
    qr_code_data = data.get('qr_code_data')
    
    if not qr_code_data:
        return jsonify({'error': 'QR code data is required'}), 400
    
    # Process QR code data
    scanner = QRScanner()
    result = scanner.scan_qr_code(qr_code_data)
    
    if result['success']:
        # Check if the scanned email belongs to a user
        recipient = User.query.filter_by(email=result['email']).first()
        if recipient:
            return jsonify({
                'success': True,
                'email': result['email'],
                'user_exists': True,
                'user_id': recipient.id
            })
        else:
            return jsonify({
                'success': True,
                'email': result['email'],
                'user_exists': False
            })
    else:
        return jsonify({'success': False, 'error': 'Invalid QR code data'}), 400

@api.route('/security-logs', methods=['GET'])
@login_required
def get_security_logs_api():
    """Get security logs (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=50)
    
    log_list = []
    for log in logs.items:
        log_list.append({
            'id': log.id,
            'user_id': log.user_id,
            'action': log.action,
            'ip_address': log.ip_address,
            'timestamp': log.timestamp.isoformat(),
            'details': log.details
        })
    
    return jsonify({
        'logs': log_list,
        'total': logs.total,
        'pages': logs.pages,
        'current_page': logs.page
    })

@api.route('/virus-scans', methods=['GET'])
@login_required
def get_virus_scans_api():
    """Get virus scan logs (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    scans = VirusScanLog.query.order_by(VirusScanLog.scanned_at.desc()).paginate(page=page, per_page=20)
    
    scan_list = []
    for scan in scans.items:
        scan_list.append({
            'id': scan.id,
            'filename': scan.filename,
            'scan_result': scan.scan_result,
            'virus_name': scan.virus_name,
            'scanned_at': scan.scanned_at.isoformat(),
            'scanned_by': scan.scanned_by
        })
    
    return jsonify({
        'scans': scan_list,
        'total': scans.total,
        'pages': scans.pages,
        'current_page': scans.page
    })

@api.route('/stats', methods=['GET'])
@login_required
def get_stats_api():
    """Get system statistics (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get statistics
    total_users = User.query.count()
    active_users = User.query.filter(User.last_login > datetime.utcnow() - timedelta(days=30)).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    total_emails = Email.query.count()
    spam_emails = Email.query.filter_by(is_spam=True).count()
    virus_scans = VirusScanLog.query.count()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'banned_users': banned_users,
        'total_emails': total_emails,
        'spam_emails': spam_emails,
        'virus_scans': virus_scans
    })


# ==================== CONTEXT MEMORY ACROSS THREADS API ====================

from ..utils.context_memory_engine import context_engine
from ..database.models import ContextMemory, ContextSummary, ContextPhrase, ContextFeedbackLog

@api.route('/email/<int:email_id>/context', methods=['GET'])
@login_required
def get_email_context(email_id):
    """Get context memory for a specific email"""
    email = Email.query.get_or_404(email_id)
    
    # Check if user has access to this email
    if email.recipient_id != current_user.id and email.sender_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get context data
    context_data = context_engine.get_context_for_email(email_id, current_user.id)
    
    return jsonify(context_data)


@api.route('/email/<int:email_id>/analyze-context', methods=['POST'])
@login_required
def analyze_email_context(email_id):
    """Trigger context analysis for an email"""
    email = Email.query.get_or_404(email_id)
    
    # Check if user has access to this email
    if email.recipient_id != current_user.id and email.sender_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Run synchronous analysis
    result = context_engine.analyze_email_sync(email_id, current_user.id)
    
    return jsonify({
        'success': True,
        'message': 'Context analysis completed',
        'result': result
    })


@api.route('/context/<int:memory_id>/feedback', methods=['POST'])
@login_required
def provide_context_feedback(memory_id):
    """Provide feedback on a context memory link"""
    data = request.get_json()
    feedback = data.get('feedback')
    
    if feedback not in ['relevant', 'not_relevant']:
        return jsonify({'error': 'Invalid feedback type. Must be "relevant" or "not_relevant"'}), 400
    
    success = context_engine.record_feedback(memory_id, current_user.id, feedback)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Feedback recorded: {feedback}'
        })
    else:
        return jsonify({'error': 'Context memory not found or access denied'}), 404


@api.route('/context/<int:memory_id>/summary', methods=['GET'])
@login_required
def get_context_summary(memory_id):
    """Get detailed summary for a context memory"""
    memory = ContextMemory.query.get_or_404(memory_id)
    
    # Check ownership
    if memory.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get summary
    summary = ContextSummary.query.filter_by(
        email_id=memory.related_email_id,
        user_id=current_user.id
    ).first()
    
    if not summary:
        return jsonify({'error': 'Summary not found'}), 404
    
    return jsonify({
        'memory_id': memory_id,
        'email_id': memory.related_email_id,
        'subject': memory.related_email.subject,
        'summary_text': summary.summary_text,
        'key_decisions': summary.key_decisions,
        'pending_tasks': summary.pending_tasks,
        'key_points': summary.key_points,
        'last_status': summary.last_status,
        'confidence': memory.overall_confidence,
        'confidence_level': memory.confidence_level
    })


@api.route('/context-phrases', methods=['GET'])
@login_required
def get_context_phrases():
    """Get all context detection phrases (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    phrases = ContextPhrase.query.filter_by(is_active=True).all()
    
    return jsonify({
        'phrases': [{
            'id': p.id,
            'phrase': p.phrase,
            'type': p.phrase_type,
            'weight': p.weight
        } for p in phrases]
    })


@api.route('/context-phrases', methods=['POST'])
@login_required
def add_context_phrase():
    """Add a new context detection phrase (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    phrase = data.get('phrase', '').lower().strip()
    phrase_type = data.get('type', 'reference')
    weight = data.get('weight', 1.0)
    
    if not phrase:
        return jsonify({'error': 'Phrase is required'}), 400
    
    # Check if already exists
    existing = ContextPhrase.query.filter_by(phrase=phrase).first()
    if existing:
        return jsonify({'error': 'Phrase already exists'}), 400
    
    new_phrase = ContextPhrase(
        phrase=phrase,
        phrase_type=phrase_type,
        weight=weight,
        is_active=True
    )
    db.session.add(new_phrase)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Phrase added successfully',
        'phrase_id': new_phrase.id
    })


@api.route('/context-phrases/<int:phrase_id>', methods=['DELETE'])
@login_required
def delete_context_phrase(phrase_id):
    """Delete a context detection phrase (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    phrase = ContextPhrase.query.get_or_404(phrase_id)
    phrase.is_active = False
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Phrase deactivated successfully'
    })


@api.route('/context-feedback-logs', methods=['GET'])
@login_required
def get_context_feedback_logs():
    """Get context feedback logs (admin only)"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    logs = ContextFeedbackLog.query.order_by(
        ContextFeedbackLog.created_at.desc()
    ).paginate(page=page, per_page=20)
    
    return jsonify({
        'logs': [{
            'id': log.id,
            'user_id': log.user_id,
            'context_memory_id': log.context_memory_id,
            'feedback_type': log.feedback_type,
            'original_confidence': log.original_confidence,
            'adjusted_confidence': log.adjusted_confidence,
            'created_at': log.created_at.isoformat()
        } for log in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': logs.page
    })


@api.route('/context-stats', methods=['GET'])
@login_required
def get_context_stats():
    """Get context memory statistics"""
    # User's own stats
    total_memories = ContextMemory.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).count()
    
    high_confidence = ContextMemory.query.filter_by(
        user_id=current_user.id,
        confidence_level='high',
        is_active=True
    ).count()
    
    medium_confidence = ContextMemory.query.filter_by(
        user_id=current_user.id,
        confidence_level='medium',
        is_active=True
    ).count()
    
    low_confidence = ContextMemory.query.filter_by(
        user_id=current_user.id,
        confidence_level='low',
        is_active=True
    ).count()
    
    feedback_given = ContextFeedbackLog.query.filter_by(
        user_id=current_user.id
    ).count()
    
    # Count unique threads (unique related_email_ids)
    from sqlalchemy import func
    active_threads = db.session.query(func.count(func.distinct(ContextMemory.related_email_id))).filter(
        ContextMemory.user_id == current_user.id,
        ContextMemory.is_active == True
    ).scalar() or 0
    
    return jsonify({
        'total_contexts': total_memories,
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'low_confidence': low_confidence,
        'feedback_given': feedback_given,
        'active_threads': active_threads
    })


@api.route('/context-links', methods=['GET'])
@login_required
def get_context_links():
    """Get context memory links for the current user"""
    memories = ContextMemory.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(ContextMemory.created_at.desc()).limit(20).all()
    
    links = []
    for m in memories:
        current_email = Email.query.get(m.current_email_id)
        related_email = Email.query.get(m.related_email_id)
        
        if current_email and related_email:
            links.append({
                'id': m.id,
                'current_email_id': m.current_email_id,
                'current_subject': current_email.subject,
                'related_email_id': m.related_email_id,
                'related_subject': related_email.subject,
                'confidence': m.overall_confidence,
                'confidence_level': m.confidence_level,
                'phrases_count': len(m.detected_phrases) if m.detected_phrases else 0,
                'created_at': m.created_at.isoformat() if m.created_at else None
            })
    
    return jsonify({'links': links})


@api.route('/context-analyze-all', methods=['POST'])
@login_required
def analyze_all_emails():
    """Analyze all emails for context memory"""
    try:
        # Get all emails for the user
        received_emails = Email.query.filter_by(recipient_id=current_user.id).all()
        sent_emails = Email.query.filter_by(sender_id=current_user.id).all()
        
        all_emails = list(set(received_emails + sent_emails))
        new_links = 0
        
        for email in all_emails:
            result = context_engine.analyze_email_sync(email.id, current_user.id)
            if result and result.get('related_count', 0) > 0:
                new_links += result.get('related_count', 0)
        
        return jsonify({
            'success': True,
            'new_links': new_links,
            'emails_analyzed': len(all_emails)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api.route('/admin/context-analyze-all', methods=['POST'])
@login_required
def admin_analyze_all_emails():
    """Admin: Analyze ALL emails in the system for context memory"""
    if not current_user.is_admin and not current_user.is_server_admin:
        return jsonify({'error': 'Access denied. Admin privileges required.'}), 403
    
    try:
        # Get ALL emails in the system
        all_emails = Email.query.filter_by(is_deleted=False).all()
        new_links = 0
        errors = 0
        
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
            except Exception as e:
                errors += 1
                continue
        
        return jsonify({
            'success': True,
            'new_links': new_links,
            'emails_analyzed': len(all_emails),
            'errors': errors
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api.route('/check-notifications', methods=['GET'])
@login_required
def check_notifications():
    """Check for new notifications (emails, reminders)"""
    # Check for unread emails
    new_emails = Email.query.filter_by(
        recipient_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).count()
    
    # Check for upcoming reminders (if reminders feature exists)
    try:
        from ..database.models import Reminder
        upcoming_reminders = Reminder.query.filter(
            Reminder.user_id == current_user.id,
            Reminder.is_completed == False,
            Reminder.reminder_time >= datetime.utcnow()
        ).count()
    except:
        upcoming_reminders = 0
    
    return jsonify({
        'new_emails': new_emails,
        'reminders': upcoming_reminders
    })


@api.route('/check-new-emails', methods=['GET'])
@login_required
def check_new_emails():
    """Check for new emails that arrived during the session"""
    # Get unread emails with details
    unread_emails = Email.query.filter_by(
        recipient_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).order_by(Email.sent_at.desc()).limit(10).all()
    
    emails_list = []
    for email in unread_emails:
        emails_list.append({
            'id': email.id,
            'subject': email.subject,
            'sender': email.sender.email if email.sender else 'Unknown',
            'sent_at': email.sent_at.timestamp() if email.sent_at else 0
        })
    
    # Check for upcoming reminders
    try:
        from ..database.models import Reminder
        upcoming_reminders = Reminder.query.filter(
            Reminder.user_id == current_user.id,
            Reminder.is_completed == False,
            Reminder.reminder_time >= datetime.utcnow()
        ).count()
    except:
        upcoming_reminders = 0
    
    return jsonify({
        'new_emails': emails_list,
        'total_unread': len(unread_emails),
        'upcoming_reminders': upcoming_reminders
    })
