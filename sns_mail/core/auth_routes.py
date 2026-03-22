from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import pyotp
from ..database.models import User, SecurityLog, VirusScanLog
from ..security.engine import SecurityEngine
from .. import db, bcrypt, limiter
from ..utils.validators import validate_email_domain, validate_password_strength, allowed_file
from ..utils.helpers import save_file, log_security_event

auth = Blueprint('auth', __name__)

@auth.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin or current_user.is_server_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('client.dashboard'))
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        totp_code = request.form.get('totp_code')
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            # Check if account is banned
            if user.is_banned:
                log_security_event(user.id, 'LOGIN_ATTEMPT_BANNED', request.remote_addr, 
                                 f"Login attempt on banned account: {user.username}")
                flash('Your account has been banned. Please contact administrator.', 'danger')
                return render_template('auth/login.html')
            
            # Check if account is locked
            if user.is_account_locked():
                flash('Account is temporarily locked due to too many failed login attempts. Please try again later.', 'danger')
                return render_template('auth/login.html')
            
            # Verify password
            if user.check_password(password):
                # Check 2FA if enabled
                if user.is_2fa_enabled:
                    if not totp_code:
                        return render_template('auth/login.html', username=username, require_2fa=True)
                    
                    if not user.verify_totp(totp_code):
                        user.login_attempts += 1
                        user.check_and_lock_account()
                        db.session.commit()
                        log_security_event(user.id, 'LOGIN_FAILED_2FA', request.remote_addr, 
                                         f"Invalid 2FA code for user: {user.username}")
                        flash('Invalid 2FA code. Please try again.', 'danger')
                        return render_template('auth/login.html', username=username, require_2fa=True)
                
                # Successful login
                user.reset_login_attempts()
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                login_user(user)
                log_security_event(user.id, 'LOGIN_SUCCESS', request.remote_addr, 
                                 f"Successful login for user: {user.username}")
                
                if user.is_admin or user.is_server_admin:
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('client.dashboard'))
            else:
                # Failed password attempt
                user.login_attempts += 1
                user.check_and_lock_account()
                db.session.commit()
                log_security_event(user.id, 'LOGIN_FAILED_PASSWORD', request.remote_addr, 
                                 f"Invalid password for user: {user.username}")
                flash('Invalid username or password.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([name, username, email, password, confirm_password]):
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/register.html')
        
        if not validate_email_domain(email):
            flash('Email must be from @snsx.com domain.', 'danger')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        
        if not validate_password_strength(password):
            flash('Password must be at least 8 characters long and contain uppercase, lowercase, and numbers.', 'danger')
            return render_template('auth/register.html')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
        
        try:
            # Handle file uploads
            face_photo = request.files.get('face_photo')
            eye_scan = request.files.get('eye_scan')
            
            face_photo_path = None
            eye_scan_path = None
            
            if face_photo and allowed_file(face_photo.filename):
                face_photo_path = save_file(face_photo, 'avatars', username)
            
            if eye_scan and allowed_file(eye_scan.filename):
                eye_scan_path = save_file(eye_scan, 'eye_scans', username)
            
            # Create user
            user = User(name=name, username=username, email=email, password=password)
            user.face_photo = face_photo_path
            user.eye_scan = eye_scan_path
            db.session.add(user)
            db.session.commit()
            
            log_security_event(user.id, 'ACCOUNT_CREATED', request.remote_addr, 
                             f"New account created: {user.username}")
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth.route('/2fa-setup')
@login_required
def setup_2fa():
    if current_user.is_2fa_enabled:
        flash('2FA is already enabled for your account.', 'info')
        return redirect(url_for('client.profile'))
    
    # Generate QR code for TOTP
    import qrcode
    from io import BytesIO
    import base64
    
    totp_uri = current_user.get_totp_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('auth/2fa_setup.html', secret=current_user.totp_secret, qr_code=qr_code)

@auth.route('/2fa-enable', methods=['POST'])
@login_required
def enable_2fa():
    totp_code = request.form.get('totp_code')
    
    if not totp_code:
        flash('Please enter the 2FA code.', 'danger')
        return redirect(url_for('auth.setup_2fa'))
    
    if current_user.verify_totp(totp_code):
        current_user.is_2fa_enabled = True
        db.session.commit()
        log_security_event(current_user.id, '2FA_ENABLED', request.remote_addr, 
                         f"2FA enabled for user: {current_user.username}")
        flash('2FA has been enabled successfully!', 'success')
        return redirect(url_for('client.profile'))
    else:
        flash('Invalid 2FA code. Please try again.', 'danger')
        return redirect(url_for('auth.setup_2fa'))

@auth.route('/2fa-disable', methods=['POST'])
@login_required
def disable_2fa():
    password = request.form.get('password')
    
    if not current_user.check_password(password):
        flash('Invalid password.', 'danger')
        return redirect(url_for('client.profile'))
    
    current_user.is_2fa_enabled = False
    db.session.commit()
    log_security_event(current_user.id, '2FA_DISABLED', request.remote_addr, 
                     f"2FA disabled for user: {current_user.username}")
    flash('2FA has been disabled.', 'info')
    return redirect(url_for('client.profile'))

@auth.route('/logout')
@login_required
def logout():
    log_security_event(current_user.id, 'LOGOUT', request.remote_addr, 
                     f"User logged out: {current_user.username}")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/security-log')
@login_required
def security_log():
    if not current_user.is_admin and not current_user.is_server_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    logs = SecurityLog.query.order_by(SecurityLog.timestamp.desc()).limit(100).all()
    return render_template('auth/security_log.html', logs=logs)

@auth.route('/api/validate-username', methods=['POST'])
def validate_username():
    username = request.json.get('username')
    if not username:
        return jsonify({'valid': False, 'message': 'Username is required'})
    
    if User.query.filter_by(username=username).first():
        return jsonify({'valid': False, 'message': 'Username already exists'})
    
    return jsonify({'valid': True, 'message': 'Username is available'})

@auth.route('/api/validate-email', methods=['POST'])
def validate_email():
    email = request.json.get('email')
    if not email:
        return jsonify({'valid': False, 'message': 'Email is required'})
    
    if not validate_email_domain(email):
        return jsonify({'valid': False, 'message': 'Email must be from @snsx.com domain'})
    
    if User.query.filter_by(email=email).first():
        return jsonify({'valid': False, 'message': 'Email already registered'})
    
    return jsonify({'valid': True, 'message': 'Email is available'})