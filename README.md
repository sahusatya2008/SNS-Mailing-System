# SNS Mail - Secure Next-Generation Email Platform

## Overview

SNS Mail is a highly secure, SNS AI based web-based email platform built with Python and Flask. It features advanced security measures including biometric authentication, QR code scanning, virus detection, and comprehensive user management. This is developed by Satya Narayan Sahu [CEO, Founder - SNSX, SAACH INDIA] and Tathoi Mondal [COO & Designer, Co-Founder - SNSX, SAACH INDIA]

## Features

### Security Features
- **Biometric Authentication**: Face photo and eye scan verification
- **Two-Factor Authentication (2FA)**: Optional TOTP-based 2FA
- **Virus Scanning**: Real-time file attachment scanning
- **Rate Limiting**: Protection against brute force attacks
- **Account Locking**: Automatic account lockout after failed attempts
- **Security Logging**: Comprehensive audit trail of all security events

### Email Features
- **Secure Email System**: Full email composition, sending, and receiving
- **Email Organization**: Inbox, sent, drafts, archive, deleted, and spam folders
- **QR Code Integration**: Unique QR codes for each user to share email addresses securely
- **Attachment Support**: Secure file attachments with virus scanning
- **Search Functionality**: Full-text search across emails
- **Email Management**: Mark as important, archive, delete, and spam reporting

### User Management
- **Role-Based Access**: Client, Admin, and Server Admin roles
- **User Registration**: Secure registration with biometric data
- **Profile Management**: Complete user profile with biometric photos
- **Account Security**: Password changes, 2FA setup, and security monitoring

### Admin Features
- **User Management**: View, ban, promote, and manage users
- **Email Monitoring**: View and manage all emails in the system
- **Security Monitoring**: View security logs and virus scan results
- **System Statistics**: Comprehensive system monitoring and reporting
- **Maintenance Tools**: System maintenance and optimization tools

### Server Admin Features
- **Advanced User Management**: Force logout, reset passwords, clear login attempts
- **Email Management**: Resend, modify, and manage emails
- **System Administration**: Server configuration and monitoring
- **Backup & Restore**: Database and file backup functionality
- **Performance Monitoring**: System performance and resource monitoring

## Technology Stack

### Backend
- **Python 3.8+**
- **Flask** - Web framework
- **Flask-SQLAlchemy** - Database ORM
- **Flask-Login** - User session management
- **Flask-Bcrypt** - Password hashing
- **Flask-Mail** - Email functionality
- **Flask-QRcode** - QR code generation
- **Flask-Limiter** - Rate limiting
- **Flask-Migrate** - Database migrations
- **PyOTP** - Two-factor authentication
- **Pillow** - Image processing
- **PyZBar** - QR code scanning
- **OpenCV** - Computer vision for QR scanning

### Frontend
- **Bootstrap 5** - Responsive UI framework
- **Font Awesome** - Icon library
- **Vanilla JavaScript** - Client-side functionality
- **HTML5 & CSS3** - Modern web standards

### Database
- **SQLite** (Development) - Default database
- **PostgreSQL** (Production) - Recommended for production

### Security
- **bcrypt** - Password hashing
- **Werkzeug** - Security utilities
- **Cryptography** - Encryption libraries
- **Magic** - File type detection

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git (for cloning)

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd sns-mail
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r sns_mail/requirements.txt
   ```

4. **Initialize the database:**
   ```bash
   python app.py init_db
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Access the application:**
   Open your browser and navigate to `http://localhost:5000`

### Docker Installation

1. **Build the Docker image:**
   ```bash
   docker build -t sns-mail .
   ```

2. **Run the container:**
   ```bash
   docker run -p 5000:5000 sns-mail
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Application Settings
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database Settings
DATABASE_URL=sqlite:///sns_mail.db

# Mail Settings
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=False

# Security Settings
MAX_CONTENT_LENGTH=16777216  # 16MB
```

### Configuration Modes

- **Development**: Debug mode enabled, SQLite database
- **Production**: Debug disabled, PostgreSQL recommended
- **Testing**: In-memory database for testing

## Usage

### Default Accounts

After initialization, two default accounts are created:

1. **Admin Account:**
   - Username: `admin`
   - Password: `Admin123!`
   - Email: `admin@snsx.com`
   - Roles: Admin, Server Admin

2. **Sample User:**
   - Username: `user1`
   - Password: `User123!`
   - Email: `user1@snsx.com`
   - Role: Client

### Key Features Walkthrough

1. **User Registration:**
   - Navigate to `/register`
   - Fill in required information
   - Upload face photo and eye scan
   - Agree to terms and create account

2. **Login:**
   - Navigate to `/login`
   - Enter username and password
   - If 2FA is enabled, enter TOTP code

3. **Email Management:**
   - Compose new emails with attachments
   - Organize emails into folders
   - Search through emails
   - Use QR codes to share email addresses

4. **Security Features:**
   - Set up 2FA in profile settings
   - View security logs
   - Monitor account activity

### Admin Panel

Access the admin panel by logging in as an admin user:

- **User Management**: View, ban, promote users
- **Email Monitoring**: Monitor all emails
- **Security Logs**: View security events
- **System Stats**: Monitor system performance

### Server Admin Panel

Access advanced server management features:

- **User Management**: Advanced user operations
- **Email Management**: Email system management
- **System Maintenance**: Server maintenance tools
- **Backup & Restore**: Data backup functionality

## Security Features

### Biometric Authentication
- **Face Recognition**: High-resolution face photos for authentication
- **Eye Scanning**: Detailed eye scans for additional security
- **Secure Storage**: Encrypted biometric data storage

### Two-Factor Authentication
- **TOTP Support**: Time-based one-time passwords
- **QR Code Setup**: Easy QR code setup for authenticator apps
- **Backup Codes**: Recovery options for lost devices

### Virus Protection
- **Real-time Scanning**: All attachments are scanned
- **Signature Detection**: Known virus signature detection
- **File Type Filtering**: Dangerous file types are blocked
- **Quarantine System**: Infected files are quarantined

### Rate Limiting
- **Login Protection**: Prevents brute force attacks
- **API Rate Limiting**: Protects API endpoints
- **IP-based Limits**: Per-IP address rate limiting

## API Documentation

The application provides a comprehensive REST API for integration:

### Authentication Endpoints
- `POST /api/user/profile` - Update user profile
- `POST /api/user/avatar` - Upload avatar
- `POST /api/user/eye-scan` - Upload eye scan
- `POST /api/user/2fa/enable` - Enable 2FA
- `POST /api/user/2fa/disable` - Disable 2FA

### Email Endpoints
- `GET /api/emails` - Get user emails
- `GET /api/email/<id>` - Get specific email
- `POST /api/compose` - Send email
- `POST /api/email/<id>/archive` - Archive email
- `POST /api/email/<id>/delete` - Delete email

### Admin Endpoints
- `GET /api/users` - Get all users
- `GET /api/security-logs` - Get security logs
- `GET /api/virus-scans` - Get virus scan results
- `POST /api/user/<id>/ban` - Ban user
- `POST /api/user/<id>/promote-admin` - Promote to admin

## File Structure

```
sns-mail/
├── app.py                          # Main application entry point
├── requirements.txt                  # Python dependencies
├── README.md                        # This file
├── sns_mail/                        # Main application package
│   ├── __init__.py                  # Package initialization
│   ├── config.py                    # Configuration settings
│   ├── core/                        # Core application logic
│   │   ├── auth_routes.py           # Authentication routes
│   │   ├── client_routes.py         # Client dashboard routes
│   │   ├── admin_routes.py          # Admin panel routes
│   │   ├── server_routes.py         # Server admin routes
│   │   ├── api_routes.py            # API endpoints
│   │   └── qr_engine.py             # QR code functionality
│   ├── database/                    # Database models and migrations
│   │   └── models.py                # SQLAlchemy models
│   ├── mail_engine/                 # Email functionality
│   │   └── smtp_server.py           # SMTP server implementation
│   ├── security/                    # Security features
│   │   └── engine.py                # Security engine
│   ├── static/                      # Static files
│   │   ├── css/                     # Stylesheets
│   │   ├── js/                      # JavaScript files
│   │   ├── images/                  # Images
│   │   └── fonts/                   # Font files
│   ├── templates/                   # HTML templates
│   │   ├── auth/                    # Authentication templates
│   │   ├── client/                  # Client templates
│   │   ├── admin/                   # Admin templates
│   │   └── server/                  # Server admin templates
│   └── utils/                       # Utility functions
│       ├── validators.py            # Input validation
│       └── helpers.py               # Helper functions
└── uploads/                         # File uploads directory
    ├── avatars/                     # User avatars
    ├── eye_scans/                   # Eye scan images
    └── attachments/                 # Email attachments
```

## Development

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_models.py

# Run with coverage
python -m pytest --cov=sns_mail
```

### Database Migrations

```bash
# Create migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback migration
flask db downgrade
```

### Code Style

The project follows PEP 8 style guidelines. Use flake8 to check code style:

```bash
flake8 sns_mail/
```

## Production Deployment

### Requirements
- **Web Server**: Nginx or Apache
- **WSGI Server**: Gunicorn or uWSGI
- **Database**: PostgreSQL
- **SSL Certificate**: HTTPS required

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Gunicorn Configuration

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Security Considerations

### Production Security
- **HTTPS Only**: Always use HTTPS in production
- **Secret Keys**: Use strong, unique secret keys
- **Database Security**: Use strong database passwords
- **File Permissions**: Restrict file system access
- **Firewall**: Configure proper firewall rules
- **Regular Updates**: Keep dependencies updated

### Data Protection
- **Encryption**: All sensitive data is encrypted
- **Backup**: Regular encrypted backups
- **Access Control**: Role-based access control
- **Audit Logs**: Comprehensive logging of all actions

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check database URL configuration
   - Ensure database server is running
   - Verify database permissions

2. **Email Sending Issues**
   - Configure SMTP server settings
   - Check mail server connectivity
   - Verify email configuration

3. **QR Code Scanning Issues**
   - Ensure camera permissions
   - Check browser compatibility
   - Verify QR code library installation

4. **Biometric Authentication Issues**
   - Check image upload permissions
   - Verify image format support
   - Ensure proper image quality

### Getting Help

- **Documentation**: Check this README for common issues
- **Issues**: Report bugs on the project repository
- **Community**: Join the discussion forums

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for your changes
5. Run the test suite
6. Submit a pull request

### Contribution Guidelines
- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Ensure backward compatibility

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Support

For support and questions:
- **Documentation**: This README and inline code comments
- **Issues**: GitHub issue tracker
- **Email**: support@snsx.com (fictional)

## Changelog

### Version 1.0.0
- Initial release
- Complete email system
- Biometric authentication
- QR code integration
- Admin and server management
- Comprehensive security features

## Acknowledgments

- Flask community for the excellent web framework
- SQLAlchemy for powerful ORM capabilities
- Bootstrap team for responsive UI components
- All contributors and testers

---

**SNS Mail** - Secure, Young Developer Designed, Next-Generation Email Platform, Smart SNS AI
