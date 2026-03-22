from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from sqlalchemy import or_, func
from ..database.models import User, Email, Draft, SentFolder, ImportantFolder, ArchiveFolder, DeletedFolder, SpamFolder, Note, SecurityLog, VirusScanLog, ContextMemory, ContextPhrase
from ..security.engine import SecurityEngine
from ..mail_engine.smtp_server import send_email
from .. import db, limiter
from ..utils.validators import validate_email_domain, allowed_file
from ..utils.helpers import save_file, log_security_event, scan_file_for_viruses
from ..core.qr_engine import QRScanner
from ..utils.sentiment_engine import track_user_mood, analyze_content

client = Blueprint('client', __name__)

@client.route('/dashboard')
@login_required
def dashboard():
    # Get email statistics
    total_emails = Email.query.filter_by(recipient_id=current_user.id, is_deleted=False).count()
    unread_emails = Email.query.filter_by(recipient_id=current_user.id, is_read=False, is_deleted=False).count()
    important_emails = Email.query.filter_by(recipient_id=current_user.id, is_important=True, is_deleted=False).count()
    sent_emails = Email.query.filter_by(sender_id=current_user.id, is_deleted=False).count()
    
    # Get recent emails
    recent_emails = Email.query.filter_by(recipient_id=current_user.id, is_deleted=False)\
        .order_by(Email.sent_at.desc()).limit(5).all()
    
    # Get recent sent emails
    recent_sent = Email.query.filter_by(sender_id=current_user.id, is_deleted=False)\
        .order_by(Email.sent_at.desc()).limit(5).all()
    
    # Get Context Memory Statistics
    context_stats = {
        'total_memories': ContextMemory.query.filter_by(user_id=current_user.id, is_active=True).count(),
        'high_confidence': ContextMemory.query.filter_by(user_id=current_user.id, confidence_level='high', is_active=True).count(),
        'medium_confidence': ContextMemory.query.filter_by(user_id=current_user.id, confidence_level='medium', is_active=True).count(),
        'low_confidence': ContextMemory.query.filter_by(user_id=current_user.id, confidence_level='low', is_active=True).count(),
        'total_phrases': ContextPhrase.query.filter_by(is_active=True).count(),
        'active_threads': db.session.query(func.count(func.distinct(ContextMemory.related_email_id))).filter(
            ContextMemory.user_id == current_user.id,
            ContextMemory.is_active == True
        ).scalar() or 0
    }
    
    # Get recent context links
    recent_contexts = ContextMemory.query.filter_by(user_id=current_user.id, is_active=True)\
        .order_by(ContextMemory.created_at.desc()).limit(10).all()
    
    return render_template('client/dashboard.html', 
                         total_emails=total_emails,
                         unread_emails=unread_emails,
                         important_emails=important_emails,
                         sent_emails=sent_emails,
                         recent_emails=recent_emails,
                         recent_sent=recent_sent,
                         context_stats=context_stats,
                         recent_contexts=recent_contexts)

@client.route('/inbox')
@login_required
def inbox():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.filter_by(recipient_id=current_user.id, is_deleted=False, is_spam=False)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/inbox.html', emails=emails)

@client.route('/important')
@login_required
def important():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.filter_by(recipient_id=current_user.id, is_important=True, is_deleted=False)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/important.html', emails=emails)

@client.route('/sent')
@login_required
def sent():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.filter_by(sender_id=current_user.id, is_deleted=False)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/sent.html', emails=emails)

@client.route('/drafts')
@login_required
def drafts():
    drafts = Draft.query.filter_by(user_id=current_user.id).order_by(Draft.updated_at.desc()).all()
    return render_template('client/drafts.html', drafts=drafts)

@client.route('/archive')
@login_required
def archive():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.join(ArchiveFolder).filter(ArchiveFolder.user_id == current_user.id)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/archive.html', emails=emails)

@client.route('/deleted')
@login_required
def deleted():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.join(DeletedFolder).filter(DeletedFolder.user_id == current_user.id)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/deleted.html', emails=emails)

@client.route('/spam')
@login_required
def spam():
    page = request.args.get('page', 1, type=int)
    emails = Email.query.filter_by(recipient_id=current_user.id, is_spam=True, is_deleted=False)\
        .order_by(Email.sent_at.desc()).paginate(page=page, per_page=20)
    return render_template('client/spam.html', emails=emails)

@client.route('/notes')
@login_required
def notes():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    return render_template('client/notes.html', notes=notes)

@client.route('/compose', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def compose():
    if request.method == 'POST':
        recipient_email = request.form.get('recipient')
        subject = request.form.get('subject')
        body = request.form.get('body')
        save_as_draft = request.form.get('save_as_draft') == 'on'
        
        # Validation
        if not recipient_email or not subject or not body:
            flash('Please fill in all required fields.', 'danger')
            return render_template('client/compose.html')
        
        # Check if recipient exists
        recipient = User.query.filter_by(email=recipient_email).first()
        if not recipient:
            flash('Recipient email not found.', 'danger')
            return render_template('client/compose.html')
        
        # Handle file upload
        attachment = request.files.get('attachment')
        attachment_path = None
        attachment_filename = None
        
        if attachment and allowed_file(attachment.filename):
            # Scan file for viruses
            scan_result = scan_file_for_viruses(attachment)
            if scan_result['infected']:
                flash(f'File contains virus: {scan_result["virus_name"]}. Email not sent.', 'danger')
                log_security_event(current_user.id, 'VIRUS_DETECTED', request.remote_addr,
                                 f"Virus detected in attachment: {attachment.filename} - {scan_result['virus_name']}")
                return render_template('client/compose.html')
            
            # Save attachment
            attachment_path = save_file(attachment, 'attachments', current_user.username)
            attachment_filename = secure_filename(attachment.filename)
        
        try:
            if save_as_draft:
                # Save as draft
                draft = Draft(
                    subject=subject,
                    body=body,
                    recipient_email=recipient_email,
                    user_id=current_user.id,
                    attachment_path=attachment_path,
                    attachment_filename=attachment_filename
                )
                db.session.add(draft)
                db.session.commit()
                flash('Draft saved successfully.', 'success')
            else:
                # Send email
                email = Email(
                    subject=subject,
                    body=body,
                    sender_id=current_user.id,
                    recipient_id=recipient.id,
                    attachment_path=attachment_path,
                    attachment_filename=attachment_filename
                )
                db.session.add(email)
                db.session.commit()
                
                # Add to sent folder
                sent_folder = SentFolder(email_id=email.id, user_id=current_user.id)
                db.session.add(sent_folder)
                db.session.commit()
                
                # Analyze sentiment for the sent email (real-time)
                try:
                    tracker = track_user_mood(current_user.id)
                    tracker.analyze_email(email)
                except Exception as e:
                    # Don't fail if sentiment analysis fails
                    print(f"Sentiment analysis failed: {e}")
                
                # Send via SMTP
                try:
                    send_email(
                        sender_email=current_user.email,
                        recipient_email=recipient.email,
                        subject=subject,
                        body=body,
                        attachment_path=attachment_path
                    )
                except Exception as e:
                    log_security_event(current_user.id, 'EMAIL_SEND_FAILED', request.remote_addr,
                                     f"Failed to send email: {str(e)}")
                
                flash('Email sent successfully!', 'success')
            
            return redirect(url_for('client.sent'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to send email. Please try again.', 'danger')
    
    return render_template('client/compose.html')

@client.route('/email/<int:email_id>')
@login_required
def view_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    # Check if user has access to this email
    if email.recipient_id != current_user.id and email.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    # Mark as read if it's incoming
    if email.recipient_id == current_user.id and not email.is_read:
        email.mark_as_read()
    
    # Analyze sentiment for incoming emails (real-time)
    if email.recipient_id == current_user.id and email.mood_score is None:
        try:
            tracker = track_user_mood(current_user.id)
            tracker.analyze_email(email)
        except Exception as e:
            # Don't fail if sentiment analysis fails
            print(f"Sentiment analysis failed: {e}")
    
    return render_template('client/view_email.html', email=email)

@client.route('/draft/<int:draft_id>')
@login_required
def view_draft(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.drafts'))
    
    return render_template('client/view_draft.html', draft=draft)

@client.route('/draft/<int:draft_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_draft(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.drafts'))
    
    if request.method == 'POST':
        draft.subject = request.form.get('subject')
        draft.body = request.form.get('body')
        draft.recipient_email = request.form.get('recipient')
        draft.updated_at = datetime.utcnow()
        
        # Handle attachment update
        attachment = request.files.get('attachment')
        if attachment and allowed_file(attachment.filename):
            # Remove old attachment if exists
            if draft.attachment_path and os.path.exists(draft.attachment_path):
                os.remove(draft.attachment_path)
            
            # Save new attachment
            draft.attachment_path = save_file(attachment, 'attachments', current_user.username)
            draft.attachment_filename = secure_filename(attachment.filename)
        
        db.session.commit()
        flash('Draft updated successfully.', 'success')
        return redirect(url_for('client.drafts'))
    
    return render_template('client/edit_draft.html', draft=draft)

@client.route('/draft/<int:draft_id>/delete', methods=['POST'])
@login_required
def delete_draft(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    
    if draft.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.drafts'))
    
    # Remove attachment if exists
    if draft.attachment_path and os.path.exists(draft.attachment_path):
        os.remove(draft.attachment_path)
    
    db.session.delete(draft)
    db.session.commit()
    flash('Draft deleted successfully.', 'success')
    return redirect(url_for('client.drafts'))

@client.route('/email/<int:email_id>/reply', methods=['GET', 'POST'])
@login_required
def reply_email(email_id):
    original_email = Email.query.get_or_404(email_id)
    
    if original_email.recipient_id != current_user.id and original_email.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        if not subject or not body:
            flash('Please fill in all required fields.', 'danger')
            return render_template('client/reply.html', original_email=original_email)
        
        try:
            # Send reply
            email = Email(
                subject=subject,
                body=body,
                sender_id=current_user.id,
                recipient_id=original_email.sender_id if original_email.recipient_id == current_user.id else original_email.recipient_id
            )
            db.session.add(email)
            db.session.commit()
            
            # Add to sent folder
            sent_folder = SentFolder(email_id=email.id, user_id=current_user.id)
            db.session.add(sent_folder)
            db.session.commit()
            
            flash('Reply sent successfully!', 'success')
            return redirect(url_for('client.sent'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to send reply. Please try again.', 'danger')
    
    reply_subject = f"Re: {original_email.subject}" if not original_email.subject.startswith('Re:') else original_email.subject
    return render_template('client/reply.html', original_email=original_email, reply_subject=reply_subject)

@client.route('/email/<int:email_id>/forward', methods=['GET', 'POST'])
@login_required
def forward_email(email_id):
    original_email = Email.query.get_or_404(email_id)
    
    if original_email.recipient_id != current_user.id and original_email.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    if request.method == 'POST':
        recipient_email = request.form.get('recipient')
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        if not recipient_email or not subject or not body:
            flash('Please fill in all required fields.', 'danger')
            return render_template('client/forward.html', original_email=original_email)
        
        # Check if recipient exists
        recipient = User.query.filter_by(email=recipient_email).first()
        if not recipient:
            flash('Recipient email not found.', 'danger')
            return render_template('client/forward.html', original_email=original_email)
        
        try:
            # Send forwarded email
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
            
            flash('Email forwarded successfully!', 'success')
            return redirect(url_for('client.sent'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to forward email. Please try again.', 'danger')
    
    forward_subject = f"Fwd: {original_email.subject}" if not original_email.subject.startswith('Fwd:') else original_email.subject
    forward_body = f"\n\n---------- Forwarded message ----------\nFrom: {original_email.sender.email}\nTo: {original_email.recipient.email}\nDate: {original_email.sent_at}\nSubject: {original_email.subject}\n\n{original_email.body}"
    return render_template('client/forward.html', original_email=original_email, forward_subject=forward_subject, forward_body=forward_body)

@client.route('/email/<int:email_id>/archive', methods=['POST'])
@login_required
def archive_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    # Add to archive folder
    if not ArchiveFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        archive_folder = ArchiveFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(archive_folder)
        db.session.commit()
        flash('Email archived successfully.', 'success')
    
    return redirect(url_for('client.inbox'))

@client.route('/email/<int:email_id>/unarchive', methods=['POST'])
@login_required
def unarchive_email(email_id):
    archive_entry = ArchiveFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first()
    
    if archive_entry:
        db.session.delete(archive_entry)
        db.session.commit()
        flash('Email removed from archive.', 'success')
    
    return redirect(url_for('client.archive'))

@client.route('/email/<int:email_id>/delete', methods=['POST'])
@login_required
def delete_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    # Add to deleted folder
    if not DeletedFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        deleted_folder = DeletedFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(deleted_folder)
        db.session.commit()
        flash('Email moved to trash.', 'success')
    
    return redirect(url_for('client.inbox'))

@client.route('/email/<int:email_id>/restore', methods=['POST'])
@login_required
def restore_email(email_id):
    deleted_entry = DeletedFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first()
    
    if deleted_entry:
        db.session.delete(deleted_entry)
        db.session.commit()
        flash('Email restored from trash.', 'success')
    
    return redirect(url_for('client.deleted'))

@client.route('/email/<int:email_id>/permanent-delete', methods=['POST'])
@login_required
def permanent_delete_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    # Remove from all folders
    ArchiveFolder.query.filter_by(email_id=email_id, user_id=current_user.id).delete()
    DeletedFolder.query.filter_by(email_id=email_id, user_id=current_user.id).delete()
    ImportantFolder.query.filter_by(email_id=email_id, user_id=current_user.id).delete()
    SpamFolder.query.filter_by(email_id=email_id, user_id=current_user.id).delete()
    
    # Remove attachment if exists
    if email.attachment_path and os.path.exists(email.attachment_path):
        os.remove(email.attachment_path)
    
    db.session.delete(email)
    db.session.commit()
    flash('Email permanently deleted.', 'success')
    
    return redirect(url_for('client.deleted'))

@client.route('/email/<int:email_id>/mark-important', methods=['POST'])
@login_required
def mark_important(email_id):
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    email.toggle_important()
    flash('Email marked as important.', 'success')
    return redirect(url_for('client.inbox'))

@client.route('/email/<int:email_id>/mark-spam', methods=['POST'])
@login_required
def mark_spam(email_id):
    email = Email.query.get_or_404(email_id)
    
    if email.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    email.mark_as_spam()
    
    # Add to spam folder
    if not SpamFolder.query.filter_by(email_id=email_id, user_id=current_user.id).first():
        spam_folder = SpamFolder(email_id=email_id, user_id=current_user.id)
        db.session.add(spam_folder)
        db.session.commit()
    
    flash('Email marked as spam.', 'success')
    return redirect(url_for('client.inbox'))

@client.route('/note/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            flash('Please fill in all required fields.', 'danger')
            return render_template('client/new_note.html')
        
        try:
            note = Note(title=title, content=content, user_id=current_user.id)
            db.session.add(note)
            db.session.commit()
            flash('Note created successfully.', 'success')
            return redirect(url_for('client.notes'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to create note. Please try again.', 'danger')
    
    return render_template('client/new_note.html')

@client.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.notes'))
    
    if request.method == 'POST':
        note.title = request.form.get('title')
        note.content = request.form.get('content')
        note.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Note updated successfully.', 'success')
        return redirect(url_for('client.notes'))
    
    return render_template('client/edit_note.html', note=note)

@client.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.notes'))
    
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully.', 'success')
    return redirect(url_for('client.notes'))

@client.route('/profile')
@login_required
def profile():
    return render_template('client/profile.html', user=current_user)

@client.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        
        if not name or not username:
            flash('Please fill in all required fields.', 'danger')
            return render_template('client/edit_profile.html')
        
        # Check if username is already taken by another user
        existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return render_template('client/edit_profile.html')
        
        current_user.name = name
        current_user.username = username
        db.session.commit()
        
        log_security_event(current_user.id, 'PROFILE_UPDATED', request.remote_addr, 
                         f"Profile updated: {current_user.username}")
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('client.profile'))
    
    return render_template('client/edit_profile.html')

@client.route('/profile/avatar', methods=['POST'])
@login_required
def update_avatar():
    avatar = request.files.get('avatar')
    
    if avatar and allowed_file(avatar.filename):
        # Remove old avatar if exists
        if current_user.face_photo and os.path.exists(current_user.face_photo):
            os.remove(current_user.face_photo)
        
        # Save new avatar
        avatar_path = save_file(avatar, 'avatars', current_user.username)
        current_user.face_photo = avatar_path
        db.session.commit()
        
        log_security_event(current_user.id, 'AVATAR_UPDATED', request.remote_addr, 
                         f"Avatar updated for user: {current_user.username}")
        flash('Avatar updated successfully.', 'success')
    
    return redirect(url_for('client.profile'))

@client.route('/profile/eye-scan', methods=['POST'])
@login_required
def update_eye_scan():
    eye_scan = request.files.get('eye_scan')
    
    if eye_scan and allowed_file(eye_scan.filename):
        # Remove old eye scan if exists
        if current_user.eye_scan and os.path.exists(current_user.eye_scan):
            os.remove(current_user.eye_scan)
        
        # Save new eye scan
        eye_scan_path = save_file(eye_scan, 'eye_scans', current_user.username)
        current_user.eye_scan = eye_scan_path
        db.session.commit()
        
        log_security_event(current_user.id, 'EYE_SCAN_UPDATED', request.remote_addr, 
                         f"Eye scan updated for user: {current_user.username}")
        flash('Eye scan updated successfully.', 'success')
    
    return redirect(url_for('client.profile'))

@client.route('/qr-scan', methods=['GET', 'POST'])
@login_required
def qr_scan():
    if request.method == 'POST':
        qr_code_data = request.form.get('qr_code_data')
        
        if qr_code_data:
            # Process QR code data
            scanner = QRScanner()
            result = scanner.scan_qr_code(qr_code_data)
            
            if result['success']:
                # Check if the scanned email belongs to a user
                recipient = User.query.filter_by(email=result['email']).first()
                if recipient:
                    return redirect(url_for('client.compose', recipient=result['email']))
                else:
                    flash('Scanned QR code does not belong to a registered user.', 'warning')
            else:
                flash('Invalid QR code data.', 'danger')
    
    return render_template('client/qr_scan.html')

@client.route('/qr-code')
@login_required
def my_qr_code():
    return render_template('client/qr_code.html', qr_code=current_user.get_qr_code())

@client.route('/search')
@login_required
def search():
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
    
    return render_template('client/search.html', emails=emails, query=query)

@client.route('/api/email/<int:email_id>/attachment')
@login_required
def download_attachment(email_id):
    email = Email.query.get_or_404(email_id)
    
    # Check if user has access to this email
    if email.recipient_id != current_user.id and email.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.inbox'))
    
    if not email.attachment_path or not os.path.exists(email.attachment_path):
        flash('Attachment not found.', 'danger')
        return redirect(url_for('client.view_email', email_id=email_id))
    
    return send_file(email.attachment_path, as_attachment=True, download_name=email.attachment_filename)