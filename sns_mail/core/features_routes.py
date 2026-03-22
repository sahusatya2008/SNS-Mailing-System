from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import json
import re
from ..database.models import (
    User, Email, Task, SubTask, VaultItem, EmailAnalytics, 
    ScheduledEmail, MoodLog, FocusSession, EmailTemplate, 
    EmailBookmark, FollowUpReminder, SecurityLog,
    CalendarEvent, EventAttendee, EventNotification
)
from .. import db, limiter
from ..utils.helpers import log_security_event

features = Blueprint('features', __name__)

# ==================== TASK MANAGEMENT ====================

@features.route('/tasks')
@login_required
def tasks():
    """View all tasks"""
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    
    query = Task.query.filter_by(user_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if priority_filter != 'all':
        query = query.filter_by(priority=priority_filter)
    
    tasks = query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    
    # Stats
    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(user_id=current_user.id, status='completed').count()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, status='pending').count()
    
    return render_template('features/tasks.html', 
                         tasks=tasks, 
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         pending_tasks=pending_tasks,
                         status_filter=status_filter,
                         priority_filter=priority_filter)


@features.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """Create a new task"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date')
        email_id = request.form.get('email_id')
        
        if not title:
            flash('Task title is required.', 'danger')
            return redirect(url_for('features.create_task'))
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        
        task = Task(
            title=title,
            description=description,
            user_id=current_user.id,
            priority=priority,
            due_date=due_date,
            email_id=email_id if email_id else None
        )
        db.session.add(task)
        db.session.commit()
        
        flash('Task created successfully!', 'success')
        return redirect(url_for('features.tasks'))
    
    return render_template('features/create_task.html')


@features.route('/tasks/<int:task_id>')
@login_required
def view_task(task_id):
    """View task details"""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.tasks'))
    
    return render_template('features/view_task.html', task=task)


@features.route('/tasks/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Update task status"""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    new_status = request.form.get('status')
    if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated'})
    
    return jsonify({'success': False, 'message': 'Invalid status'}), 400


@features.route('/tasks/<int:task_id>/add-subtask', methods=['POST'])
@login_required
def add_subtask(task_id):
    """Add a subtask"""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    title = request.form.get('title')
    if title:
        subtask = SubTask(task_id=task_id, title=title)
        db.session.add(subtask)
        db.session.commit()
        return jsonify({'success': True, 'id': subtask.id})
    
    return jsonify({'success': False, 'message': 'Title required'}), 400


@features.route('/subtasks/<int:subtask_id>/toggle', methods=['POST'])
@login_required
def toggle_subtask(subtask_id):
    """Toggle subtask completion"""
    subtask = SubTask.query.get_or_404(subtask_id)
    task = Task.query.get(subtask.task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    subtask.is_completed = not subtask.is_completed
    if subtask.is_completed:
        subtask.completed_at = datetime.utcnow()
    else:
        subtask.completed_at = None
    db.session.commit()
    
    return jsonify({'success': True, 'completed': subtask.is_completed})


@features.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    """Delete a task"""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.tasks'))
    
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.', 'success')
    return redirect(url_for('features.tasks'))


# ==================== SECURE VAULT ====================

@features.route('/vault')
@login_required
def vault():
    """View secure vault"""
    items = VaultItem.query.filter_by(user_id=current_user.id).order_by(VaultItem.created_at.desc()).all()
    return render_template('features/vault.html', items=items)


@features.route('/vault/add', methods=['GET', 'POST'])
@login_required
def add_vault_item():
    """Add item to vault"""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        item_type = request.form.get('item_type', 'note')
        email_id = request.form.get('email_id')
        auto_delete_days = request.form.get('auto_delete_days')
        
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('features.add_vault_item'))
        
        # Simple encryption (in production, use proper encryption)
        import hashlib
        key_hash = hashlib.sha256(f"{current_user.id}{datetime.utcnow().timestamp()}".encode()).hexdigest()
        
        auto_delete_at = None
        if auto_delete_days:
            auto_delete_at = datetime.utcnow() + timedelta(days=int(auto_delete_days))
        
        item = VaultItem(
            user_id=current_user.id,
            title=title,
            content=content,  # Should be encrypted in production
            item_type=item_type,
            email_id=email_id if email_id else None,
            encryption_key_hash=key_hash,
            auto_delete_at=auto_delete_at
        )
        db.session.add(item)
        db.session.commit()
        
        log_security_event(current_user.id, 'VAULT_ITEM_ADDED', request.remote_addr,
                         f"Vault item '{title}' added")
        
        flash('Item added to vault successfully!', 'success')
        return redirect(url_for('features.vault'))
    
    return render_template('features/add_vault_item.html')


@features.route('/vault/<int:item_id>')
@login_required
def view_vault_item(item_id):
    """View vault item"""
    item = VaultItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.vault'))
    
    # Update access tracking
    item.last_accessed = datetime.utcnow()
    item.access_count += 1
    db.session.commit()
    
    return render_template('features/view_vault_item.html', item=item)


@features.route('/vault/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_vault_item(item_id):
    """Delete vault item"""
    item = VaultItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.vault'))
    
    db.session.delete(item)
    db.session.commit()
    
    log_security_event(current_user.id, 'VAULT_ITEM_DELETED', request.remote_addr,
                     f"Vault item '{item.title}' deleted")
    
    flash('Vault item deleted successfully.', 'success')
    return redirect(url_for('features.vault'))


# ==================== EMAIL SCHEDULER ====================

@features.route('/scheduled')
@login_required
def scheduled_emails():
    """View scheduled emails"""
    emails = ScheduledEmail.query.filter_by(
        user_id=current_user.id, 
        is_sent=False, 
        is_cancelled=False
    ).order_by(ScheduledEmail.scheduled_at.asc()).all()
    
    sent_emails = ScheduledEmail.query.filter_by(
        user_id=current_user.id, 
        is_sent=True
    ).order_by(ScheduledEmail.sent_at.desc()).limit(10).all()
    
    return render_template('features/scheduled_emails.html', 
                         emails=emails, 
                         sent_emails=sent_emails)


@features.route('/scheduled/create', methods=['GET', 'POST'])
@login_required
def create_scheduled_email():
    """Create a scheduled email"""
    if request.method == 'POST':
        recipient = request.form.get('recipient')
        subject = request.form.get('subject')
        body = request.form.get('body')
        scheduled_at_str = request.form.get('scheduled_at')
        smart_schedule = request.form.get('smart_schedule') == 'on'
        
        if not all([recipient, subject, body, scheduled_at_str]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('features.create_scheduled_email'))
        
        try:
            scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('features.create_scheduled_email'))
        
        if scheduled_at <= datetime.utcnow():
            flash('Scheduled time must be in the future.', 'danger')
            return redirect(url_for('features.create_scheduled_email'))
        
        scheduled = ScheduledEmail(
            user_id=current_user.id,
            recipient_email=recipient,
            subject=subject,
            body=body,
            scheduled_at=scheduled_at,
            is_smart_scheduled=smart_schedule
        )
        db.session.add(scheduled)
        db.session.commit()
        
        flash('Email scheduled successfully!', 'success')
        return redirect(url_for('features.scheduled_emails'))
    
    return render_template('features/create_scheduled_email.html')


@features.route('/scheduled/<int:email_id>/cancel', methods=['POST'])
@login_required
def cancel_scheduled_email(email_id):
    """Cancel a scheduled email"""
    email = ScheduledEmail.query.get_or_404(email_id)
    if email.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.scheduled_emails'))
    
    if email.is_sent:
        flash('Cannot cancel an already sent email.', 'danger')
        return redirect(url_for('features.scheduled_emails'))
    
    email.is_cancelled = True
    db.session.commit()
    
    flash('Scheduled email cancelled.', 'success')
    return redirect(url_for('features.scheduled_emails'))


@features.route('/scheduled/<int:email_id>/send-now', methods=['POST'])
@login_required
def send_scheduled_email_now(email_id):
    """Send a scheduled email immediately"""
    scheduled = ScheduledEmail.query.get_or_404(email_id)
    
    if scheduled.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.scheduled_emails'))
    
    if scheduled.is_sent:
        flash('Email already sent.', 'warning')
        return redirect(url_for('features.scheduled_emails'))
    
    if scheduled.is_cancelled:
        flash('Cannot send a cancelled email.', 'danger')
        return redirect(url_for('features.scheduled_emails'))
    
    # Find the recipient
    recipient = User.query.filter_by(email=scheduled.recipient_email).first()
    
    if not recipient:
        flash('Recipient not found in the system.', 'danger')
        return redirect(url_for('features.scheduled_emails'))
    
    try:
        # Create the email
        email = Email(
            subject=scheduled.subject,
            body=scheduled.body,
            sender_id=current_user.id,
            recipient_id=recipient.id,
            attachment_path=scheduled.attachment_path,
            attachment_filename=scheduled.attachment_filename
        )
        db.session.add(email)
        
        # Mark scheduled email as sent
        scheduled.is_sent = True
        scheduled.sent_at = datetime.utcnow()
        
        db.session.commit()
        
        # Try to send via SMTP
        try:
            from ..mail_engine.smtp_server import send_email
            send_email(
                sender_email=current_user.email,
                recipient_email=recipient.email,
                subject=scheduled.subject,
                body=scheduled.body,
                attachment_path=scheduled.attachment_path
            )
        except Exception as e:
            # SMTP failed, but email is saved in system
            pass
        
        flash('Email sent successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to send email. Please try again.', 'danger')
    
    return redirect(url_for('features.scheduled_emails'))


# ==================== FOCUS MODE ====================

@features.route('/focus')
@login_required
def focus_mode():
    """Focus mode dashboard"""
    active_session = FocusSession.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).first()
    
    recent_sessions = FocusSession.query.filter_by(
        user_id=current_user.id, 
        is_active=False
    ).order_by(FocusSession.started_at.desc()).limit(10).all()
    
    # Stats
    total_focus_time = db.session.query(db.func.sum(FocusSession.duration_minutes)).filter(
        FocusSession.user_id == current_user.id,
        FocusSession.is_active == False
    ).scalar() or 0
    
    total_sessions = FocusSession.query.filter_by(
        user_id=current_user.id, 
        is_active=False
    ).count()
    
    return render_template('features/focus_mode.html',
                         active_session=active_session,
                         recent_sessions=recent_sessions,
                         total_focus_time=total_focus_time,
                         total_sessions=total_sessions)


@features.route('/focus/start', methods=['POST'])
@login_required
def start_focus_session():
    """Start a focus session"""
    # Check for existing active session
    existing = FocusSession.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).first()
    
    if existing:
        flash('You already have an active focus session.', 'warning')
        return redirect(url_for('features.focus_mode'))
    
    session = FocusSession(
        user_id=current_user.id,
        blocked_notifications=True
    )
    
    # Update user focus mode
    current_user.focus_mode_enabled = True
    current_user.focus_mode_until = datetime.utcnow() + timedelta(hours=1)
    
    db.session.add(session)
    db.session.commit()
    
    flash('Focus session started! Stay focused!', 'success')
    return redirect(url_for('features.focus_mode'))


@features.route('/focus/end', methods=['POST'])
@login_required
def end_focus_session():
    """End focus session"""
    session = FocusSession.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).first()
    
    if not session:
        flash('No active focus session found.', 'warning')
        return redirect(url_for('features.focus_mode'))
    
    session.is_active = False
    session.ended_at = datetime.utcnow()
    session.duration_minutes = int((session.ended_at - session.started_at).total_seconds() / 60)
    
    current_user.focus_mode_enabled = False
    current_user.focus_mode_until = None
    
    db.session.commit()
    
    flash(f'Focus session ended! You focused for {session.duration_minutes} minutes.', 'success')
    return redirect(url_for('features.focus_mode'))


# ==================== EMAIL TEMPLATES ====================

@features.route('/templates')
@login_required
def templates():
    """View email templates"""
    user_templates = EmailTemplate.query.filter_by(user_id=current_user.id).order_by(EmailTemplate.use_count.desc()).all()
    return render_template('features/templates.html', templates=user_templates)


@features.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Create email template"""
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        body = request.form.get('body')
        category = request.form.get('category', 'personal')
        variables = request.form.get('variables', '')
        
        if not all([name, subject, body]):
            flash('Name, subject, and body are required.', 'danger')
            return redirect(url_for('features.create_template'))
        
        # Parse variables
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        
        template = EmailTemplate(
            user_id=current_user.id,
            name=name,
            subject=subject,
            body=body,
            category=category,
            variables=json.dumps(var_list) if var_list else None
        )
        db.session.add(template)
        db.session.commit()
        
        flash('Template created successfully!', 'success')
        return redirect(url_for('features.templates'))
    
    return render_template('features/create_template.html')


@features.route('/templates/<int:template_id>/use')
@login_required
def use_template(template_id):
    """Use a template for composing"""
    template = EmailTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.templates'))
    
    # Increment use count
    template.use_count += 1
    db.session.commit()
    
    # Redirect to compose with template data
    return redirect(url_for('client.compose', 
                          template_id=template_id,
                          subject=template.subject,
                          body=template.body))


@features.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """Edit an existing template"""
    template = EmailTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.templates'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        body = request.form.get('body')
        category = request.form.get('category', 'personal')
        variables = request.form.get('variables', '')
        
        if not all([name, subject, body]):
            flash('Name, subject, and body are required.', 'danger')
            return redirect(url_for('features.edit_template', template_id=template_id))
        
        # Parse variables
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        
        template.name = name
        template.subject = subject
        template.body = body
        template.category = category
        template.variables = json.dumps(var_list) if var_list else None
        
        db.session.commit()
        flash('Template updated successfully!', 'success')
        return redirect(url_for('features.templates'))
    
    return render_template('features/create_template.html', template=template)


@features.route('/templates/api/<int:template_id>')
@login_required
def get_template_api(template_id):
    """API endpoint to get template data"""
    template = EmailTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': template.id,
        'name': template.name,
        'subject': template.subject,
        'body': template.body,
        'category': template.category,
        'variables': template.variables,
        'use_count': template.use_count
    })


@features.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    """Delete a template"""
    template = EmailTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.templates'))
    
    db.session.delete(template)
    db.session.commit()
    
    flash('Template deleted successfully.', 'success')
    return redirect(url_for('features.templates'))


@features.route('/templates/designer')
@login_required
def template_designer():
    """Email template designer"""
    template_id = request.args.get('template_id')
    template = None
    if template_id:
        template = EmailTemplate.query.get_or_404(int(template_id))
        if template.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('features.templates'))
    return render_template('features/template_designer.html', template=template)


@features.route('/templates/save-design', methods=['POST'])
@login_required
def save_template_design():
    """Save template from designer"""
    template_id = request.form.get('template_id')
    name = request.form.get('name')
    subject = request.form.get('subject')
    body = request.form.get('body')
    category = request.form.get('category', 'personal')
    
    if not all([name, subject, body]):
        flash('Name, subject, and body are required.', 'danger')
        return redirect(url_for('features.template_designer'))
    
    # Extract variables from body
    import re
    variables = re.findall(r'\{\{(\w+)\}\}', body)
    variables = list(set(variables))  # Remove duplicates
    
    if template_id:
        # Update existing template
        template = EmailTemplate.query.get_or_404(int(template_id))
        if template.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('features.templates'))
        template.name = name
        template.subject = subject
        template.body = body
        template.category = category
        template.variables = json.dumps(variables) if variables else None
    else:
        # Create new template
        template = EmailTemplate(
            user_id=current_user.id,
            name=name,
            subject=subject,
            body=body,
            category=category,
            variables=json.dumps(variables) if variables else None
        )
        db.session.add(template)
    
    db.session.commit()
    flash('Template saved successfully!', 'success')
    return redirect(url_for('features.templates'))


# ==================== ANALYTICS ====================

@features.route('/analytics')
@login_required
def analytics():
    """Email analytics dashboard"""
    # Get last 30 days of analytics
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    analytics_data = EmailAnalytics.query.filter(
        EmailAnalytics.user_id == current_user.id,
        EmailAnalytics.date >= thirty_days_ago
    ).order_by(EmailAnalytics.date.desc()).all()
    
    # Calculate totals
    total_sent = sum(a.emails_sent for a in analytics_data)
    total_received = sum(a.emails_received for a in analytics_data)
    total_read = sum(a.emails_read for a in analytics_data)
    avg_productivity = sum(a.productivity_score for a in analytics_data) / len(analytics_data) if analytics_data else 0
    
    # Get today's analytics or create
    today = datetime.utcnow().date()
    today_analytics = EmailAnalytics.query.filter(
        EmailAnalytics.user_id == current_user.id,
        db.func.date(EmailAnalytics.date) == today
    ).first()
    
    return render_template('features/analytics.html',
                         analytics_data=analytics_data,
                         total_sent=total_sent,
                         total_received=total_received,
                         total_read=total_read,
                         avg_productivity=avg_productivity,
                         today_analytics=today_analytics)


# ==================== MOOD TRACKING ====================

@features.route('/mood')
@login_required
def mood_tracking():
    """Mood tracking dashboard with comprehensive AI analysis"""
    from ..utils.sentiment_engine import track_user_mood
    from ..database.models import SentimentAnalysis, MoodInsight, CommunicationPattern
    
    # Get the comprehensive mood report
    tracker = track_user_mood(current_user.id)
    report = tracker.get_comprehensive_mood_report(days=30)
    
    # Get last 30 days of mood data
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    mood_data = MoodLog.query.filter(
        MoodLog.user_id == current_user.id,
        MoodLog.date >= thirty_days_ago
    ).order_by(MoodLog.date.desc()).all()
    
    # Get recent sentiment analyses
    recent_analyses = SentimentAnalysis.query.filter(
        SentimentAnalysis.user_id == current_user.id,
        SentimentAnalysis.analyzed_at >= thirty_days_ago
    ).order_by(SentimentAnalysis.analyzed_at.desc()).limit(50).all()
    
    # Get unread insights
    unread_insights = MoodInsight.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_dismissed=False
    ).order_by(MoodInsight.created_at.desc()).all()
    
    # Get communication patterns
    patterns = CommunicationPattern.query.filter_by(
        user_id=current_user.id
    ).order_by(CommunicationPattern.strength.desc()).limit(10).all()
    
    # Calculate averages
    avg_incoming = sum(m.avg_incoming_mood for m in mood_data if m.avg_incoming_mood) / len([m for m in mood_data if m.avg_incoming_mood]) if mood_data else 0
    avg_outgoing = sum(m.avg_outgoing_mood for m in mood_data if m.avg_outgoing_mood) / len([m for m in mood_data if m.avg_outgoing_mood]) if mood_data else 0
    
    # Calculate emotion distribution for chart
    emotion_chart_data = {}
    for analysis in recent_analyses:
        if analysis.emotion_scores:
            try:
                scores = json.loads(analysis.emotion_scores)
                for emotion, score in scores.items():
                    if emotion not in emotion_chart_data:
                        emotion_chart_data[emotion] = 0
                    emotion_chart_data[emotion] += score
            except:
                pass
    
    # Sort emotions by score
    emotion_chart_data = dict(sorted(emotion_chart_data.items(), key=lambda x: x[1], reverse=True)[:10])
    
    # Calculate sentiment timeline for chart
    sentiment_timeline = []
    for log in reversed(mood_data):
        sentiment_timeline.append({
            'date': log.date.strftime('%Y-%m-%d') if log.date else '',
            'incoming': round(log.avg_incoming_mood, 3) if log.avg_incoming_mood else 0,
            'outgoing': round(log.avg_outgoing_mood, 3) if log.avg_outgoing_mood else 0,
            'trend': log.mood_trend or 'stable'
        })
    
    return render_template('features/mood_tracking.html',
                         mood_data=mood_data,
                         avg_incoming=avg_incoming,
                         avg_outgoing=avg_outgoing,
                         report=report,
                         recent_analyses=recent_analyses,
                         unread_insights=unread_insights,
                         patterns=patterns,
                         emotion_chart_data=emotion_chart_data,
                         sentiment_timeline=json.dumps(sentiment_timeline))


@features.route('/mood/api/analyze', methods=['POST'])
@login_required
def analyze_text_api():
    """API endpoint to analyze text sentiment in real-time"""
    from ..utils.sentiment_engine import analyze_content
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '')
    else:
        text = request.form.get('text', '')
    
    if not text or not text.strip():
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    try:
        analysis = analyze_content(text)
        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@features.route('/mood/api/analysis/<int:analysis_id>')
@login_required
def get_analysis_detail(analysis_id):
    """Get detailed analysis for a specific sentiment analysis"""
    from ..database.models import SentimentAnalysis
    
    analysis = SentimentAnalysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Parse JSON fields
    result = {
        'id': analysis.id,
        'sentiment_score': analysis.sentiment_score,
        'sentiment_label': analysis.sentiment_label,
        'confidence': analysis.confidence,
        'positive_score': analysis.positive_score,
        'negative_score': analysis.negative_score,
        'neutral_score': analysis.neutral_score,
        'emotion_scores': json.loads(analysis.emotion_scores) if analysis.emotion_scores else {},
        'emotion_percentages': json.loads(analysis.emotion_percentages) if analysis.emotion_percentages else {},
        'dominant_emotions': json.loads(analysis.dominant_emotions) if analysis.dominant_emotions else [],
        'urgency_level': analysis.urgency_level,
        'formality_level': analysis.formality_level,
        'text_statistics': json.loads(analysis.text_statistics) if analysis.text_statistics else {},
        'insights': json.loads(analysis.insights) if analysis.insights else [],
        'is_outgoing': analysis.is_outgoing,
        'analyzed_at': analysis.analyzed_at.isoformat() if analysis.analyzed_at else None
    }
    
    # Get related content
    if analysis.email_id:
        email = Email.query.get(analysis.email_id)
        if email:
            result['email'] = {
                'id': email.id,
                'subject': email.subject,
                'sender': email.sender.username if email.sender else 'Unknown',
                'recipient': email.recipient.username if email.recipient else 'Unknown',
                'sent_at': email.sent_at.isoformat() if email.sent_at else None
            }
    
    return jsonify(result)


@features.route('/mood/insights/<int:insight_id>/dismiss', methods=['POST'])
@login_required
def dismiss_mood_insight(insight_id):
    """Dismiss a mood insight"""
    from ..database.models import MoodInsight
    
    insight = MoodInsight.query.get_or_404(insight_id)
    if insight.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    insight.is_dismissed = True
    db.session.commit()
    
    return jsonify({'success': True})


@features.route('/mood/insights/<int:insight_id>/read', methods=['POST'])
@login_required
def mark_insight_read(insight_id):
    """Mark an insight as read"""
    from ..database.models import MoodInsight
    
    insight = MoodInsight.query.get_or_404(insight_id)
    if insight.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    insight.is_read = True
    insight.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


# ==================== FOLLOW-UP REMINDERS ====================

@features.route('/reminders')
@login_required
def reminders():
    """View follow-up reminders"""
    active_reminders = FollowUpReminder.query.filter_by(
        user_id=current_user.id,
        is_dismissed=False,
        reminder_sent=False
    ).order_by(FollowUpReminder.reminder_at.asc()).all()
    
    past_reminders = FollowUpReminder.query.filter_by(
        user_id=current_user.id
    ).filter(
        (FollowUpReminder.reminder_sent == True) | 
        (FollowUpReminder.is_dismissed == True)
    ).order_by(FollowUpReminder.reminder_at.desc()).limit(20).all()
    
    # Get upcoming calendar events with reminders
    upcoming_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= datetime.utcnow(),
        CalendarEvent.status == 'scheduled',
        (CalendarEvent.reminder_one_day == True) | 
        (CalendarEvent.reminder_one_hour == True) |
        (CalendarEvent.reminder_custom != None)
    ).order_by(CalendarEvent.start_time.asc()).limit(20).all()
    
    # Get event notifications
    event_notifications = EventNotification.query.filter(
        EventNotification.user_id == current_user.id,
        EventNotification.is_sent == True,
        EventNotification.is_read == False
    ).order_by(EventNotification.sent_at.desc()).all()
    
    return render_template('features/reminders.html',
                         active_reminders=active_reminders,
                         past_reminders=past_reminders,
                         upcoming_events=upcoming_events,
                         event_notifications=event_notifications)


@features.route('/reminders/create', methods=['POST'])
@login_required
def create_reminder():
    """Create a follow-up reminder"""
    email_id = request.form.get('email_id')
    task_id = request.form.get('task_id')
    reminder_at_str = request.form.get('reminder_at')
    notes = request.form.get('notes')
    
    if not reminder_at_str:
        flash('Reminder time is required.', 'danger')
        return redirect(url_for('features.reminders'))
    
    try:
        reminder_at = datetime.strptime(reminder_at_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('features.reminders'))
    
    reminder = FollowUpReminder(
        user_id=current_user.id,
        email_id=email_id if email_id else None,
        task_id=task_id if task_id else None,
        reminder_at=reminder_at,
        notes=notes
    )
    db.session.add(reminder)
    db.session.commit()
    
    flash('Reminder created successfully!', 'success')
    return redirect(url_for('features.reminders'))


@features.route('/reminders/<int:reminder_id>/dismiss', methods=['POST'])
@login_required
def dismiss_reminder(reminder_id):
    """Dismiss a reminder"""
    reminder = FollowUpReminder.query.get_or_404(reminder_id)
    if reminder.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    reminder.is_dismissed = True
    db.session.commit()
    
    return jsonify({'success': True})


@features.route('/reminders/<int:reminder_id>/snooze', methods=['POST'])
@login_required
def snooze_reminder(reminder_id):
    """Snooze a reminder"""
    reminder = FollowUpReminder.query.get_or_404(reminder_id)
    if reminder.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    minutes = request.form.get('minutes', 30, type=int)
    reminder.reminder_at = datetime.utcnow() + timedelta(minutes=minutes)
    reminder.snooze_count += 1
    db.session.commit()
    
    return jsonify({'success': True, 'new_time': reminder.reminder_at.isoformat()})


# ==================== BOOKMARKS ====================

@features.route('/bookmarks')
@login_required
def bookmarks():
    """View bookmarked emails"""
    bookmarks = EmailBookmark.query.filter_by(user_id=current_user.id).order_by(EmailBookmark.created_at.desc()).all()
    return render_template('features/bookmarks.html', bookmarks=bookmarks)


@features.route('/emails/<int:email_id>/bookmark', methods=['POST'])
@login_required
def bookmark_email(email_id):
    """Bookmark an email"""
    email = Email.query.get_or_404(email_id)
    
    # Check if already bookmarked
    existing = EmailBookmark.query.filter_by(user_id=current_user.id, email_id=email_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'bookmarked': False})
    
    bookmark_type = request.form.get('type', 'pin')
    color = request.form.get('color', 'blue')
    notes = request.form.get('notes', '')
    
    bookmark = EmailBookmark(
        user_id=current_user.id,
        email_id=email_id,
        bookmark_type=bookmark_type,
        color=color,
        notes=notes
    )
    db.session.add(bookmark)
    db.session.commit()
    
    return jsonify({'bookmarked': True})


# ==================== SELF-DESTRUCTING EMAILS ====================

@features.route('/emails/self-destruct', methods=['POST'])
@login_required
def create_self_destructing():
    """Create a self-destructing email"""
    recipient_email = request.form.get('recipient')
    subject = request.form.get('subject')
    body = request.form.get('body')
    destruct_type = request.form.get('destruct_type', 'after_read')
    destruct_hours = request.form.get('destruct_hours', 24, type=int)
    
    # Find recipient
    recipient = User.query.filter_by(email=recipient_email).first()
    if not recipient:
        flash('Recipient not found.', 'danger')
        return redirect(url_for('client.compose'))
    
    destruct_at = None
    destruct_after_read = False
    
    if destruct_type == 'after_read':
        destruct_after_read = True
    else:
        destruct_at = datetime.utcnow() + timedelta(hours=destruct_hours)
    
    email = Email(
        subject=subject,
        body=body,
        sender_id=current_user.id,
        recipient_id=recipient.id,
        is_self_destructing=True,
        destruct_after_read=destruct_after_read,
        destruct_at=destruct_at
    )
    db.session.add(email)
    db.session.commit()
    
    flash('Self-destructing email sent!', 'success')
    return redirect(url_for('client.inbox'))


# ==================== CALENDAR & EVENTS ====================

@features.route('/calendar')
@login_required
def calendar():
    """Calendar view with events and meetings"""
    # Get current month's events
    today = datetime.utcnow()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get events for current and next month
    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= start_of_month,
        CalendarEvent.status != 'cancelled'
    ).order_by(CalendarEvent.start_time.asc()).all()
    
    # Get upcoming events for sidebar
    upcoming_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= datetime.utcnow(),
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).limit(10).all()
    
    # Get today's events
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= today_start,
        CalendarEvent.start_time < today_end,
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).all()
    
    # Get upcoming meetings
    upcoming_meetings = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.is_meeting == True,
        CalendarEvent.start_time >= datetime.utcnow(),
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).limit(5).all()
    
    # Stats
    total_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.status != 'cancelled'
    ).count()
    
    total_meetings = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.is_meeting == True,
        CalendarEvent.status != 'cancelled'
    ).count()
    
    # Convert events to JSON-serializable format
    events_json = [{
        'id': e.id,
        'title': e.title,
        'start_time': e.start_time.isoformat() if e.start_time else None,
        'end_time': e.end_time.isoformat() if e.end_time else None,
        'event_type': e.event_type,
        'color': e.color,
        'is_meeting': e.is_meeting,
        'location': e.location,
        'status': e.status
    } for e in events]
    
    return render_template('features/calendar.html',
                         events=events_json,
                         upcoming_events=upcoming_events,
                         today_events=today_events,
                         upcoming_meetings=upcoming_meetings,
                         total_events=total_events,
                         total_meetings=total_meetings,
                         today=today)


@features.route('/calendar/events')
@login_required
def get_calendar_events():
    """API endpoint to get events for calendar display"""
    start = request.args.get('start')
    end = request.args.get('end')
    
    query = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.status != 'cancelled'
    )
    
    if start:
        try:
            start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
            query = query.filter(CalendarEvent.start_time >= start_date)
        except:
            pass
    
    if end:
        try:
            end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
            query = query.filter(CalendarEvent.start_time <= end_date)
        except:
            pass
    
    events = query.all()
    
    events_list = []
    for event in events:
        events_list.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_time.isoformat(),
            'end': event.end_time.isoformat() if event.end_time else None,
            'allDay': event.is_all_day,
            'color': event.color,
            'url': f'/features/calendar/event/{event.id}',
            'extendedProps': {
                'type': event.event_type,
                'isMeeting': event.is_meeting,
                'location': event.location,
                'status': event.status
            }
        })
    
    return jsonify(events_list)


@features.route('/calendar/event/<int:event_id>')
@login_required
def view_event(event_id):
    """View event details"""
    event = CalendarEvent.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.calendar'))
    
    # Get attendees
    attendees = EventAttendee.query.filter_by(event_id=event_id).all()
    
    # Calculate time remaining
    time_remaining = None
    if event.start_time > datetime.utcnow():
        delta = event.start_time - datetime.utcnow()
        time_remaining = {
            'days': delta.days,
            'hours': delta.seconds // 3600,
            'minutes': (delta.seconds % 3600) // 60,
            'seconds': delta.seconds % 60,
            'total_seconds': delta.total_seconds()
        }
    
    return render_template('features/view_event.html',
                         event=event,
                         attendees=attendees,
                         time_remaining=time_remaining)


@features.route('/calendar/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """Create a new event"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        event_type = request.form.get('event_type', 'event')
        
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        is_all_day = request.form.get('is_all_day') == 'on'
        
        # Meeting specific
        is_meeting = request.form.get('is_meeting') == 'on'
        meeting_link = request.form.get('meeting_link')
        meeting_platform = request.form.get('meeting_platform')
        attendees = request.form.getlist('attendees')
        
        # Reminder settings
        reminder_one_day = request.form.get('reminder_one_day') == 'on'
        reminder_one_hour = request.form.get('reminder_one_hour') == 'on'
        reminder_custom = request.form.get('reminder_custom', type=int)
        
        # Color
        color = request.form.get('color', '#00d4ff')
        
        # Linking
        task_id = request.form.get('task_id')
        email_id = request.form.get('email_id')
        reminder_id = request.form.get('reminder_id')
        
        if not title or not start_time_str:
            flash('Title and start time are required.', 'danger')
            return redirect(url_for('features.create_event'))
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid start time format.', 'danger')
            return redirect(url_for('features.create_event'))
        
        end_time = None
        if end_time_str:
            try:
                end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            except:
                pass
        
        event = CalendarEvent(
            user_id=current_user.id,
            title=title,
            description=description,
            location=location,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            is_all_day=is_all_day,
            is_meeting=is_meeting,
            meeting_link=meeting_link,
            meeting_platform=meeting_platform,
            attendee_ids=json.dumps(attendees) if attendees else None,
            reminder_one_day=reminder_one_day,
            reminder_one_hour=reminder_one_hour,
            reminder_custom=reminder_custom,
            color=color,
            task_id=task_id if task_id else None,
            email_id=email_id if email_id else None,
            reminder_id=reminder_id if reminder_id else None
        )
        db.session.add(event)
        db.session.commit()
        
        # Add attendees
        for attendee_email in attendees:
            if attendee_email:
                attendee_user = User.query.filter_by(email=attendee_email).first()
                event_attendee = EventAttendee(
                    event_id=event.id,
                    user_id=attendee_user.id if attendee_user else None,
                    email=attendee_email
                )
                db.session.add(event_attendee)
        
        db.session.commit()
        
        # Create notifications for reminders
        if reminder_one_day:
            notification = EventNotification(
                user_id=current_user.id,
                event_id=event.id,
                notification_type='one_day',
                scheduled_time=start_time - timedelta(days=1),
                title=f'Event Tomorrow: {title}',
                message=f'You have "{title}" scheduled for tomorrow at {start_time.strftime("%H:%M")}'
            )
            db.session.add(notification)
        
        if reminder_one_hour:
            notification = EventNotification(
                user_id=current_user.id,
                event_id=event.id,
                notification_type='one_hour',
                scheduled_time=start_time - timedelta(hours=1),
                title=f'Event in 1 Hour: {title}',
                message=f'You have "{title}" starting in 1 hour'
            )
            db.session.add(notification)
        
        if reminder_custom:
            notification = EventNotification(
                user_id=current_user.id,
                event_id=event.id,
                notification_type='custom',
                scheduled_time=start_time - timedelta(minutes=reminder_custom),
                title=f'Event in {reminder_custom} minutes: {title}',
                message=f'You have "{title}" starting soon'
            )
            db.session.add(notification)
        
        db.session.commit()
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('features.view_event', event_id=event.id))
    
    # GET request - show form
    # Get tasks for linking
    tasks = Task.query.filter_by(user_id=current_user.id, status='pending').order_by(Task.due_date.asc()).limit(20).all()
    
    # Get users for attendee selection
    users = User.query.filter(User.id != current_user.id).limit(50).all()
    
    # Pre-fill from query params
    prefill = {
        'title': request.args.get('title'),
        'start_time': request.args.get('start_time'),
        'end_time': request.args.get('end_time'),
        'task_id': request.args.get('task_id'),
        'email_id': request.args.get('email_id')
    }
    
    return render_template('features/create_event.html',
                         tasks=tasks,
                         users=users,
                         prefill=prefill)


@features.route('/calendar/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Edit an event"""
    event = CalendarEvent.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.calendar'))
    
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.location = request.form.get('location')
        event.event_type = request.form.get('event_type', 'event')
        
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        event.is_all_day = request.form.get('is_all_day') == 'on'
        
        event.is_meeting = request.form.get('is_meeting') == 'on'
        event.meeting_link = request.form.get('meeting_link')
        event.meeting_platform = request.form.get('meeting_platform')
        
        event.reminder_one_day = request.form.get('reminder_one_day') == 'on'
        event.reminder_one_hour = request.form.get('reminder_one_hour') == 'on'
        event.reminder_custom = request.form.get('reminder_custom', type=int)
        
        event.color = request.form.get('color', '#00d4ff')
        
        if start_time_str:
            try:
                event.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            except:
                pass
        
        if end_time_str:
            try:
                event.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            except:
                event.end_time = None
        
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('features.view_event', event_id=event.id))
    
    # GET request
    tasks = Task.query.filter_by(user_id=current_user.id, status='pending').limit(20).all()
    users = User.query.filter(User.id != current_user.id).limit(50).all()
    
    return render_template('features/create_event.html',
                         event=event,
                         tasks=tasks,
                         users=users,
                         edit_mode=True)


@features.route('/calendar/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete an event"""
    event = CalendarEvent.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('features.calendar'))
    
    # Delete associated notifications
    EventNotification.query.filter_by(event_id=event_id).delete()
    EventAttendee.query.filter_by(event_id=event_id).delete()
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Event deleted successfully.', 'success')
    return redirect(url_for('features.calendar'))


@features.route('/calendar/event/<int:event_id>/cancel', methods=['POST'])
@login_required
def cancel_event(event_id):
    """Cancel an event"""
    event = CalendarEvent.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    event.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'success': True})


@features.route('/calendar/event/<int:event_id>/complete', methods=['POST'])
@login_required
def complete_event(event_id):
    """Mark event as completed"""
    event = CalendarEvent.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    event.status = 'completed'
    db.session.commit()
    
    return jsonify({'success': True})


# ==================== SCHEDULE POPUP & NOTIFICATIONS ====================

@features.route('/calendar/schedule-popup')
@login_required
def get_schedule_popup():
    """Get schedule popup data for logged-in users"""
    today = datetime.utcnow()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get today's events
    today_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= today_start,
        CalendarEvent.start_time < today_end,
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).all()
    
    # Get upcoming events in next 7 days
    week_end = today_start + timedelta(days=7)
    upcoming_events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= today_end,
        CalendarEvent.start_time < week_end,
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).all()
    
    # Get pending reminders
    pending_reminders = FollowUpReminder.query.filter(
        FollowUpReminder.user_id == current_user.id,
        FollowUpReminder.reminder_at <= today + timedelta(hours=1),
        FollowUpReminder.is_dismissed == False,
        FollowUpReminder.reminder_sent == False
    ).order_by(FollowUpReminder.reminder_at.asc()).all()
    
    # Get unread event notifications
    unread_notifications = EventNotification.query.filter(
        EventNotification.user_id == current_user.id,
        EventNotification.is_sent == True,
        EventNotification.is_read == False
    ).order_by(EventNotification.sent_at.desc()).limit(5).all()
    
    # Check if popup should be shown
    show_popup = len(today_events) > 0 or len(pending_reminders) > 0 or len(unread_notifications) > 0
    
    return jsonify({
        'show_popup': show_popup,
        'today_events': [e.to_dict() for e in today_events],
        'upcoming_events': [e.to_dict() for e in upcoming_events],
        'pending_reminders': [{
            'id': r.id,
            'notes': r.notes,
            'reminder_at': r.reminder_at.isoformat()
        } for r in pending_reminders],
        'unread_notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type
        } for n in unread_notifications]
    })


@features.route('/calendar/notifications')
@login_required
def get_event_notifications():
    """Get all event notifications for the user"""
    notifications = EventNotification.query.filter(
        EventNotification.user_id == current_user.id,
        EventNotification.is_sent == True
    ).order_by(EventNotification.sent_at.desc()).limit(20).all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type,
            'is_read': n.is_read,
            'sent_at': n.sent_at.isoformat() if n.sent_at else None,
            'event_id': n.event_id
        } for n in notifications]
    })


@features.route('/calendar/notification/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    notification = EventNotification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@features.route('/calendar/upcoming')
@login_required
def get_upcoming_schedules():
    """Get upcoming schedules with running timers"""
    now = datetime.utcnow()
    
    # Get events in next 24 hours
    next_24h = now + timedelta(hours=24)
    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_time >= now,
        CalendarEvent.start_time <= next_24h,
        CalendarEvent.status == 'scheduled'
    ).order_by(CalendarEvent.start_time.asc()).all()
    
    # Get reminders in next 24 hours
    reminders = FollowUpReminder.query.filter(
        FollowUpReminder.user_id == current_user.id,
        FollowUpReminder.reminder_at >= now,
        FollowUpReminder.reminder_at <= next_24h,
        FollowUpReminder.is_dismissed == False
    ).order_by(FollowUpReminder.reminder_at.asc()).all()
    
    schedules = []
    
    for event in events:
        delta = event.start_time - now
        schedules.append({
            'id': event.id,
            'type': 'event',
            'title': event.title,
            'start_time': event.start_time.isoformat(),
            'is_meeting': event.is_meeting,
            'location': event.location,
            'meeting_link': event.meeting_link,
            'time_remaining': {
                'total_seconds': delta.total_seconds(),
                'days': delta.days,
                'hours': delta.seconds // 3600,
                'minutes': (delta.seconds % 3600) // 60,
                'seconds': delta.seconds % 60
            }
        })
    
    for reminder in reminders:
        delta = reminder.reminder_at - now
        schedules.append({
            'id': reminder.id,
            'type': 'reminder',
            'title': reminder.notes or 'Reminder',
            'start_time': reminder.reminder_at.isoformat(),
            'time_remaining': {
                'total_seconds': delta.total_seconds(),
                'days': delta.days,
                'hours': delta.seconds // 3600,
                'minutes': (delta.seconds % 3600) // 60,
                'seconds': delta.seconds % 60
            }
        })
    
    # Sort by time remaining
    schedules.sort(key=lambda x: x['time_remaining']['total_seconds'])
    
    return jsonify({'schedules': schedules})
