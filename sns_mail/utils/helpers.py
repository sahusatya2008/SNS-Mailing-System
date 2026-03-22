import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from ..database.models import SecurityLog
from .. import db

logger = logging.getLogger(__name__)

def save_file(file, folder_type, username):
    """
    Save uploaded file to appropriate directory
    
    Args:
        file: File object from request
        folder_type (str): Type of folder (avatars, eye_scans, attachments)
        username (str): Username for folder organization
    
    Returns:
        str: Path to saved file
    """
    try:
        if not file or not file.filename:
            return None
        
        # Sanitize filename
        filename = secure_filename(file.filename)
        if not filename:
            return None
        
        # Create user-specific directory
        user_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_type, username)
        os.makedirs(user_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        # Save file
        file_path = os.path.join(user_dir, unique_filename)
        file.save(file_path)
        
        logger.info(f"File saved: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return None

def delete_file(file_path):
    """
    Delete file from filesystem
    
    Args:
        file_path (str): Path to file to delete
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File deleted: {file_path}")
            return True
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
    
    return False

def get_file_size(file_path):
    """
    Get file size in bytes
    
    Args:
        file_path (str): Path to file
    
    Returns:
        int: File size in bytes, 0 if file doesn't exist
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error getting file size: {e}")
    
    return 0

def get_file_type(file_path):
    """
    Get file type/mime type
    
    Args:
        file_path (str): Path to file
    
    Returns:
        str: File type or 'unknown'
    """
    try:
        import magic
        return magic.from_file(file_path, mime=True)
    except ImportError:
        logger.warning("python-magic not installed, using extension-based detection")
        return os.path.splitext(file_path)[1].lower()
    except Exception as e:
        logger.error(f"Error getting file type: {e}")
        return 'unknown'

def format_file_size(size_bytes):
    """
    Format file size in human-readable format
    
    Args:
        size_bytes (int): File size in bytes
    
    Returns:
        str: Formatted file size
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def log_security_event(user_id, action, ip_address, details):
    """
    Log security event to database
    
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
        
        logger.info(f"Security event: {action} - {details}")
        
    except Exception as e:
        logger.error(f"Error logging security event: {e}")

def generate_unique_filename(original_filename, prefix=""):
    """
    Generate unique filename with timestamp
    
    Args:
        original_filename (str): Original filename
        prefix (str): Optional prefix
    
    Returns:
        str: Unique filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    name, ext = os.path.splitext(original_filename)
    
    if prefix:
        return f"{prefix}_{timestamp}{ext}"
    else:
        return f"{name}_{timestamp}{ext}"

def cleanup_old_files(directory, max_age_days=30):
    """
    Clean up old files from directory
    
    Args:
        directory (str): Directory to clean
        max_age_days (int): Maximum age in days
    
    Returns:
        int: Number of files deleted
    """
    try:
        if not os.path.exists(directory):
            return 0
        
        deleted_count = 0
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            if os.path.isfile(file_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mtime < cutoff_time:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting old file {file_path}: {e}")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return 0

def validate_file_integrity(file_path, expected_size=None):
    """
    Validate file integrity
    
    Args:
        file_path (str): Path to file
        expected_size (int): Expected file size in bytes
    
    Returns:
        bool: True if file is valid, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        if expected_size is not None:
            actual_size = os.path.getsize(file_path)
            if actual_size != expected_size:
                return False
        
        # Check if file is readable
        with open(file_path, 'rb') as f:
            f.read(1)
        
        return True
        
    except Exception as e:
        logger.error(f"File integrity check failed: {e}")
        return False

def get_directory_size(directory):
    """
    Get total size of directory in bytes
    
    Args:
        directory (str): Directory path
    
    Returns:
        int: Total size in bytes
    """
    total_size = 0
    
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
    except Exception as e:
        logger.error(f"Error calculating directory size: {e}")
    
    return total_size

def create_thumbnail(image_path, thumbnail_path, size=(128, 128)):
    """
    Create thumbnail from image
    
    Args:
        image_path (str): Path to original image
        thumbnail_path (str): Path to save thumbnail
        size (tuple): Thumbnail size
    
    Returns:
        bool: True if thumbnail created successfully, False otherwise
    """
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path, 'JPEG')
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        return False

def scan_file_for_viruses(file_path):
    """
    Scan file for viruses (placeholder for actual antivirus integration)
    
    Args:
        file_path (str): Path to file to scan
    
    Returns:
        dict: Scan result with infected status and virus name
    """
    # This is a placeholder implementation
    # In a real application, you would integrate with an actual antivirus engine
    
    try:
        # Basic checks
        file_size = os.path.getsize(file_path)
        
        # Check for suspicious file extensions
        suspicious_extensions = ['.exe', '.bat', '.scr', '.vbs', '.js', '.jar']
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in suspicious_extensions:
            return {
                'infected': True,
                'virus_name': 'Suspicious file type',
                'scan_result': 'BLOCKED'
            }
        
        # Check file magic numbers (basic PE file detection)
        with open(file_path, 'rb') as f:
            header = f.read(2)
        
        if header == b'MZ':  # DOS/Windows executable
            return {
                'infected': True,
                'virus_name': 'Executable file detected',
                'scan_result': 'BLOCKED'
            }
        
        return {
            'infected': False,
            'virus_name': None,
            'scan_result': 'CLEAN'
        }
        
    except Exception as e:
        logger.error(f"Error scanning file: {e}")
        return {
            'infected': True,
            'virus_name': 'Scan error',
            'scan_result': 'ERROR'
        }

def format_datetime(dt):
    """
    Format datetime in human-readable format
    
    Args:
        dt (datetime): Datetime object
    
    Returns:
        str: Formatted datetime string
    """
    if dt is None:
        return "N/A"
    
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')

def sanitize_html_input(text):
    """
    Basic HTML sanitization (placeholder for proper HTML sanitization)
    
    Args:
        text (str): Input text
    
    Returns:
        str: Sanitized text
    """
    # This is a basic implementation
    # In production, use a proper HTML sanitization library like bleach
    
    if not text:
        return ""
    
    # Remove potentially dangerous tags
    dangerous_tags = ['<script', '<iframe', '<object', '<embed', '<form']
    for tag in dangerous_tags:
        text = text.replace(tag, '<' + tag[1:])
    
    return text

def generate_random_string(length=32):
    """
    Generate random string
    
    Args:
        length (int): Length of string
    
    Returns:
        str: Random string
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_client_ip(request_obj):
    """
    Get client IP address from request
    
    Args:
        request_obj: Flask request object
    
    Returns:
        str: Client IP address
    """
    # Check for forwarded headers
    if request_obj.headers.get('X-Forwarded-For'):
        return request_obj.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request_obj.headers.get('X-Real-IP'):
        return request_obj.headers.get('X-Real-IP')
    else:
        return request_obj.remote_addr

def format_user_activity_log(user_id, action, details):
    """
    Format user activity log entry
    
    Args:
        user_id (int): User ID
        action (str): Action performed
        details (str): Additional details
    
    Returns:
        str: Formatted log entry
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    return f"[{timestamp}] User {user_id}: {action} - {details}"