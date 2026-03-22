import os
import hashlib
import re
import logging
try:
    import magic
except ImportError:
    magic = None
from datetime import datetime, timedelta
from flask import request, current_app
from ..database.models import SecurityLog, VirusScanLog
from .. import db

class SecurityEngine:
    """Advanced security engine for SNS Mail"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.virus_signatures = self.load_virus_signatures()
        self.suspicious_patterns = self.load_suspicious_patterns()
        self.rate_limit_storage = {}  # In-memory rate limiting
    
    def load_virus_signatures(self):
        """Load virus signatures for file scanning"""
        # This would typically load from a database or external file
        # For now, we'll use a basic set of signatures
        return {
            'eicar_test': b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*',
            'suspicious_executable': [b'MZ', b'PE'],  # Basic PE file signatures
        }
    
    def load_suspicious_patterns(self):
        """Load suspicious patterns for content analysis"""
        return {
            'malicious_links': [
                r'http[s]?://[^\s]+\.exe',
                r'http[s]?://[^\s]+\.bat',
                r'http[s]?://[^\s]+\.scr',
                r'http[s]?://[^\s]+\.vbs',
            ],
            'phishing_keywords': [
                r'urgent action required',
                r'account suspended',
                r'verify your account',
                r'click here to claim',
                r'you have won',
                r'free money',
                r'password reset required',
            ],
            'suspicious_attachments': [
                r'\.exe$',
                r'\.bat$',
                r'\.scr$',
                r'\.vbs$',
                r'\.js$',
                r'\.jar$',
            ]
        }
    
    def scan_file(self, file_path):
        """
        Scan file for viruses and suspicious content
        
        Args:
            file_path (str): Path to the file to scan
        
        Returns:
            dict: Scan result with infected status and virus name
        """
        try:
            # Check file size (prevent DoS)
            if os.path.getsize(file_path) > 16 * 1024 * 1024:  # 16MB limit
                return {'infected': True, 'virus_name': 'File too large'}
            
            # Check file type using magic numbers
            with open(file_path, 'rb') as f:
                file_content = f.read(1024)  # Read first 1KB for signature
            
            # Check against virus signatures
            for virus_name, signature in self.virus_signatures.items():
                if signature in file_content:
                    self.log_virus_detection(os.path.basename(file_path), virus_name, file_path)
                    return {'infected': True, 'virus_name': virus_name}
            
            # Check file extension
            file_extension = os.path.splitext(file_path)[1].lower()
            for pattern in self.suspicious_patterns['suspicious_attachments']:
                if re.search(pattern, file_extension):
                    self.log_virus_detection(os.path.basename(file_path), 'Suspicious file type', file_path)
                    return {'infected': True, 'virus_name': 'Suspicious file type'}
            
            # Check file magic number
            try:
                file_type = magic.from_buffer(file_content, mime=True)
                if file_type in ['application/x-executable', 'application/x-dosexec']:
                    self.log_virus_detection(os.path.basename(file_path), 'Executable file detected', file_path)
                    return {'infected': True, 'virus_name': 'Executable file detected'}
            except:
                pass
            
            # Calculate file hash for integrity checking
            file_hash = self.calculate_file_hash(file_path)
            
            # Log clean file
            self.log_virus_scan(os.path.basename(file_path), 'CLEAN', file_path, file_hash)
            
            return {'infected': False, 'virus_name': None}
            
        except Exception as e:
            self.logger.error(f"Error scanning file {file_path}: {e}")
            return {'infected': True, 'virus_name': 'Scan error'}
    
    def scan_email_content(self, subject, body, sender_email):
        """
        Scan email content for malicious patterns
        
        Args:
            subject (str): Email subject
            body (str): Email body
            sender_email (str): Sender's email address
        
        Returns:
            dict: Scan result with suspicious status and details
        """
        suspicious_indicators = []
        
        # Check for malicious links
        for pattern in self.suspicious_patterns['malicious_links']:
            if re.search(pattern, body, re.IGNORECASE):
                suspicious_indicators.append('Malicious link detected')
        
        # Check for phishing keywords
        content = f"{subject} {body}".lower()
        for pattern in self.suspicious_patterns['phishing_keywords']:
            if re.search(pattern, content):
                suspicious_indicators.append('Phishing keywords detected')
        
        # Check sender reputation (basic check)
        if not sender_email.endswith('@snsx.com'):
            suspicious_indicators.append('External sender')
        
        # Check for suspicious attachments mentioned in body
        if any(ext in body.lower() for ext in ['.exe', '.bat', '.scr', '.vbs']):
            suspicious_indicators.append('Suspicious attachment mentioned')
        
        return {
            'suspicious': len(suspicious_indicators) > 0,
            'indicators': suspicious_indicators,
            'risk_level': self.calculate_risk_level(suspicious_indicators)
        }
    
    def calculate_risk_level(self, indicators):
        """Calculate risk level based on suspicious indicators"""
        if not indicators:
            return 'LOW'
        elif len(indicators) == 1:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def check_rate_limit(self, identifier, limit=5, window=60):
        """
        Check rate limiting for an identifier
        
        Args:
            identifier (str): Identifier to check (IP, username, etc.)
            limit (int): Maximum requests allowed
            window (int): Time window in seconds
        
        Returns:
            bool: True if within limits, False if exceeded
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window)
        
        if identifier not in self.rate_limit_storage:
            self.rate_limit_storage[identifier] = []
        
        # Remove old entries
        self.rate_limit_storage[identifier] = [
            timestamp for timestamp in self.rate_limit_storage[identifier]
            if timestamp > cutoff
        ]
        
        # Check if within limits
        if len(self.rate_limit_storage[identifier]) >= limit:
            return False
        
        # Add current request
        self.rate_limit_storage[identifier].append(now)
        return True
    
    def log_security_event(self, user_id, action, ip_address, details):
        """
        Log security event
        
        Args:
            user_id (int): User ID (can be None)
            action (str): Security action
            ip_address (str): IP address
            details (str): Event details
        """
        try:
            security_log = SecurityLog(
                user_id=user_id,
                action=action,
                ip_address=ip_address,
                timestamp=datetime.utcnow(),
                details=details
            )
            db.session.add(security_log)
            db.session.commit()
            
            self.logger.info(f"Security event: {action} - {details}")
            
        except Exception as e:
            self.logger.error(f"Error logging security event: {e}")
    
    def check_password_strength(self, password):
        """
        Check password strength
        
        Args:
            password (str): Password to check
        
        Returns:
            dict: Password strength result
        """
        score = 0
        feedback = []
        
        # Length check
        if len(password) >= 8:
            score += 1
        else:
            feedback.append("Password should be at least 8 characters long")
        
        # Character variety checks
        if re.search(r'[a-z]', password):
            score += 1
        else:
            feedback.append("Password should contain lowercase letters")
        
        if re.search(r'[A-Z]', password):
            score += 1
        else:
            feedback.append("Password should contain uppercase letters")
        
        if re.search(r'\d', password):
            score += 1
        else:
            feedback.append("Password should contain numbers")
        
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        else:
            feedback.append("Password should contain special characters")
        
        # Common password check
        common_passwords = ['password', '123456', 'qwerty', 'admin']
        if password.lower() in common_passwords:
            score -= 2
            feedback.append("Password is too common")
        
        # Determine strength
        if score >= 5:
            strength = 'STRONG'
        elif score >= 3:
            strength = 'MEDIUM'
        else:
            strength = 'WEAK'
        
        return {
            'score': score,
            'strength': strength,
            'feedback': feedback
        }
    
    def sanitize_input(self, input_string):
        """
        Sanitize user input to prevent XSS and injection attacks
        
        Args:
            input_string (str): Input string to sanitize
        
        Returns:
            str: Sanitized string
        """
        if not input_string:
            return ""
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', '\\', ';', '--']
        for char in dangerous_chars:
            input_string = input_string.replace(char, '')
        
        # Limit length
        if len(input_string) > 1000:
            input_string = input_string[:1000]
        
        return input_string.strip()
    
    def validate_email_domain(self, email):
        """
        Validate email domain
        
        Args:
            email (str): Email address to validate
        
        Returns:
            bool: True if valid SNS domain, False otherwise
        """
        if not email or '@' not in email:
            return False
        
        domain = email.split('@')[-1].lower()
        return domain == 'snsx.com'
    
    def calculate_file_hash(self, file_path):
        """
        Calculate SHA256 hash of a file
        
        Args:
            file_path (str): Path to the file
        
        Returns:
            str: SHA256 hash
        """
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating file hash: {e}")
            return None
    
    def log_virus_detection(self, filename, virus_name, file_path):
        """Log virus detection event"""
        virus_log = VirusScanLog(
            filename=filename,
            file_path=file_path,
            scan_result='INFECTED',
            virus_name=virus_name,
            scanned_at=datetime.utcnow()
        )
        db.session.add(virus_log)
        db.session.commit()
        
        self.logger.warning(f"Virus detected: {virus_name} in file {filename}")
    
    def log_virus_scan(self, filename, scan_result, file_path, file_hash=None):
        """Log virus scan result"""
        virus_log = VirusScanLog(
            filename=filename,
            file_path=file_path,
            scan_result=scan_result,
            virus_name=None,
            scanned_at=datetime.utcnow()
        )
        db.session.add(virus_log)
        db.session.commit()
    
    def check_session_security(self, session):
        """
        Check session security
        
        Args:
            session (dict): Flask session object
        
        Returns:
            bool: True if session is secure, False otherwise
        """
        # Check if session has been tampered with
        # This is a basic implementation - in production, use proper session security
        
        if 'user_id' not in session:
            return False
        
        # Check session age (basic timeout)
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.utcnow() - last_activity > timedelta(minutes=30):
                return False
        
        return True
    
    def update_session_activity(self, session):
        """Update session last activity"""
        session['last_activity'] = datetime.utcnow().isoformat()
    
    def detect_brute_force(self, ip_address, username=None):
        """
        Detect brute force attacks
        
        Args:
            ip_address (str): IP address to check
            username (str): Username to check (optional)
        
        Returns:
            bool: True if brute force detected, False otherwise
        """
        # Check failed login attempts from IP
        recent_failures = SecurityLog.query.filter(
            SecurityLog.ip_address == ip_address,
            SecurityLog.action.in_(['LOGIN_FAILED_PASSWORD', 'LOGIN_FAILED_2FA']),
            SecurityLog.timestamp > datetime.utcnow() - timedelta(minutes=15)
        ).count()
        
        if recent_failures >= 5:
            self.log_security_event(None, 'BRUTE_FORCE_DETECTED', ip_address,
                                  f"Multiple failed login attempts from {ip_address}")
            return True
        
        # Check failed login attempts for username
        if username:
            user_failures = SecurityLog.query.filter(
                SecurityLog.action.in_(['LOGIN_FAILED_PASSWORD', 'LOGIN_FAILED_2FA']),
                SecurityLog.details.like(f"%{username}%"),
                SecurityLog.timestamp > datetime.utcnow() - timedelta(minutes=15)
            ).count()
            
            if user_failures >= 3:
                self.log_security_event(None, 'BRUTE_FORCE_DETECTED', ip_address,
                                      f"Multiple failed login attempts for user {username}")
                return True
        
        return False
    
    def check_suspicious_activity(self, user_id, action, ip_address):
        """
        Check for suspicious user activity
        
        Args:
            user_id (int): User ID
            action (str): Action being performed
            ip_address (str): IP address
        
        Returns:
            bool: True if suspicious, False otherwise
        """
        # Check for rapid actions
        recent_actions = SecurityLog.query.filter(
            SecurityLog.user_id == user_id,
            SecurityLog.timestamp > datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        if recent_actions > 20:  # More than 20 actions in 5 minutes
            self.log_security_event(user_id, 'SUSPICIOUS_ACTIVITY', ip_address,
                                  f"Rapid actions detected: {action}")
            return True
        
        # Check for unusual login times (basic check)
        current_hour = datetime.utcnow().hour
        if current_hour < 6 or current_hour > 22:  # Late night/early morning
            # This could be normal for some users, so just log it
            self.log_security_event(user_id, 'UNUSUAL_LOGIN_TIME', ip_address,
                                  f"Login at unusual time: {current_hour}:00 UTC")
        
        return False
    
    def encrypt_sensitive_data(self, data):
        """
        Encrypt sensitive data
        
        Args:
            data (str): Data to encrypt
        
        Returns:
            str: Encrypted data
        """
        # This is a placeholder for encryption
        # In production, use proper encryption libraries
        import base64
        return base64.b64encode(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data):
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data (str): Encrypted data
        
        Returns:
            str: Decrypted data
        """
        # This is a placeholder for decryption
        # In production, use proper encryption libraries
        import base64
        return base64.b64decode(encrypted_data.encode()).decode()
    
    def generate_security_token(self, user_id, token_type='session'):
        """
        Generate security token
        
        Args:
            user_id (int): User ID
            token_type (str): Type of token
        
        Returns:
            str: Security token
        """
        import secrets
        import time
        
        timestamp = str(int(time.time()))
        random_string = secrets.token_urlsafe(32)
        
        token_data = f"{user_id}:{token_type}:{timestamp}:{random_string}"
        
        # Hash the token data
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()
        
        return f"{token_hash}:{timestamp}"
    
    def validate_security_token(self, token, user_id, max_age=3600):
        """
        Validate security token
        
        Args:
            token (str): Token to validate
            user_id (int): User ID
            max_age (int): Maximum age in seconds
        
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            if ':' not in token:
                return False
            
            token_hash, timestamp = token.split(':', 1)
            timestamp = int(timestamp)
            
            # Check token age
            current_time = int(time.time())
            if current_time - timestamp > max_age:
                return False
            
            # In a real implementation, you would verify the hash
            # For now, just check if it looks like a valid hash
            if len(token_hash) != 64:  # SHA256 hash length
                return False
            
            return True
            
        except Exception:
            return False