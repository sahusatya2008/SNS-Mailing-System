import re
import os
from werkzeug.utils import secure_filename

def validate_email_domain(email):
    """
    Validate that email is from @snsx.com domain
    
    Args:
        email (str): Email address to validate
    
    Returns:
        bool: True if valid SNS domain, False otherwise
    """
    if not email or '@' not in email:
        return False
    
    domain = email.split('@')[-1].lower()
    return domain == 'snsx.com'

def validate_password_strength(password):
    """
    Validate password strength
    
    Args:
        password (str): Password to validate
    
    Returns:
        bool: True if password is strong enough, False otherwise
    """
    if len(password) < 8:
        return False
    
    # Check for uppercase, lowercase, and numbers
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    return has_upper and has_lower and has_digit

def validate_username(username):
    """
    Validate username format
    
    Args:
        username (str): Username to validate
    
    Returns:
        bool: True if username is valid, False otherwise
    """
    if not username:
        return False
    
    # Username should be 3-50 characters, alphanumeric and underscores only
    if len(username) < 3 or len(username) > 50:
        return False
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False
    
    # Should not start with number
    if username[0].isdigit():
        return False
    
    return True

def validate_name(name):
    """
    Validate name format
    
    Args:
        name (str): Name to validate
    
    Returns:
        bool: True if name is valid, False otherwise
    """
    if not name or len(name.strip()) < 2:
        return False
    
    # Name should contain only letters, spaces, and hyphens
    if not re.match(r'^[a-zA-Z\s\-\'\.]+$', name):
        return False
    
    return True

def allowed_file(filename):
    """
    Check if file extension is allowed
    
    Args:
        filename (str): Filename to check
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'bmp'}
    
    if not filename:
        return False
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file_path, max_size_mb=16):
    """
    Validate file size
    
    Args:
        file_path (str): Path to file
        max_size_mb (int): Maximum file size in MB
    
    Returns:
        bool: True if file size is within limits, False otherwise
    """
    try:
        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        return file_size <= max_size_bytes
    except OSError:
        return False

def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename (str): Original filename
    
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return None
    
    # Use werkzeug's secure_filename
    sanitized = secure_filename(filename)
    
    # Additional checks
    if not sanitized or sanitized == '.' or sanitized == '..':
        return None
    
    # Check for suspicious patterns
    suspicious_patterns = ['../', '..\\', '/etc/', '/var/', '/usr/', 'C:\\', 'C:/']
    for pattern in suspicious_patterns:
        if pattern in sanitized:
            return None
    
    return sanitized

def validate_url(url):
    """
    Validate URL format
    
    Args:
        url (str): URL to validate
    
    Returns:
        bool: True if URL is valid, False otherwise
    """
    if not url:
        return False
    
    # Basic URL validation regex
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:[-\w.]|(?:%[\da-fA-F]{2}))+'  # domain name
        r'(?::\d+)?'  # optional port
        r'(?:[/?:].*)?$'  # path, query, fragment
    )
    
    return bool(url_pattern.match(url))

def validate_ip_address(ip):
    """
    Validate IP address format
    
    Args:
        ip (str): IP address to validate
    
    Returns:
        bool: True if IP address is valid, False otherwise
    """
    if not ip:
        return False
    
    # IPv4 validation
    ipv4_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    # IPv6 validation (simplified)
    ipv6_pattern = re.compile(
        r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    )
    
    return bool(ipv4_pattern.match(ip) or ipv6_pattern.match(ip))

def validate_subject(subject):
    """
    Validate email subject
    
    Args:
        subject (str): Email subject
    
    Returns:
        bool: True if subject is valid, False otherwise
    """
    if not subject:
        return False
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', ';', '--']
    for char in dangerous_chars:
        if char in subject:
            return False
    
    # Limit length
    if len(subject) > 200:
        return False
    
    return True

def validate_body(body):
    """
    Validate email body
    
    Args:
        body (str): Email body
    
    Returns:
        bool: True if body is valid, False otherwise
    """
    if not body:
        return False
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', ';', '--']
    for char in dangerous_chars:
        if char in body:
            return False
    
    # Limit length
    if len(body) > 10000:  # 10KB limit
        return False
    
    return True

def validate_recipient_email(email):
    """
    Validate recipient email format
    
    Args:
        email (str): Recipient email
    
    Returns:
        bool: True if email is valid, False otherwise
    """
    if not email:
        return False
    
    # Basic email validation regex
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    return bool(email_pattern.match(email))

def validate_search_query(query):
    """
    Validate search query
    
    Args:
        query (str): Search query
    
    Returns:
        bool: True if query is valid, False otherwise
    """
    if not query:
        return False
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', ';', '--']
    for char in dangerous_chars:
        if char in query:
            return False
    
    # Limit length
    if len(query) > 100:
        return False
    
    return True

def validate_note_title(title):
    """
    Validate note title
    
    Args:
        title (str): Note title
    
    Returns:
        bool: True if title is valid, False otherwise
    """
    if not title:
        return False
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', ';', '--']
    for char in dangerous_chars:
        if char in title:
            return False
    
    # Limit length
    if len(title) > 100:
        return False
    
    return True

def validate_note_content(content):
    """
    Validate note content
    
    Args:
        content (str): Note content
    
    Returns:
        bool: True if content is valid, False otherwise
    """
    if not content:
        return False
    
    # Limit length
    if len(content) > 50000:  # 50KB limit
        return False
    
    return True

def validate_qr_code_data(data):
    """
    Validate QR code data
    
    Args:
        data (str): QR code data
    
    Returns:
        bool: True if data is valid, False otherwise
    """
    if not data:
        return False
    
    # Check if it looks like an email
    if '@snsx.com' not in data:
        return False
    
    # Validate email format
    return validate_recipient_email(data)

def validate_admin_action(action):
    """
    Validate admin action
    
    Args:
        action (str): Admin action
    
    Returns:
        bool: True if action is valid, False otherwise
    """
    valid_actions = [
        'ban_user', 'unban_user', 'promote_admin', 'demote_admin',
        'promote_server_admin', 'demote_server_admin', 'delete_email',
        'mark_spam', 'unmark_spam', 'clear_logs', 'scan_viruses'
    ]
    
    return action in valid_actions

def validate_server_action(action):
    """
    Validate server admin action
    
    Args:
        action (str): Server admin action
    
    Returns:
        bool: True if action is valid, False otherwise
    """
    valid_actions = [
        'reset_password', 'force_logout', 'clear_login_attempts',
        'resend_email', 'modify_email', 'quarantine_virus',
        'create_backup', 'restore_backup', 'optimize_database'
    ]
    
    return action in valid_actions