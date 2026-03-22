from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_qrcode import QRcode
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import atexit
import json
from datetime import timedelta
from markupsafe import Markup

# Initialize extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
qrcode = QRcode()
limiter = Limiter(key_func=get_remote_address)

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(app.instance_path, 'sns_mail.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Mail configuration
    app.config['MAIL_SERVER'] = 'localhost'
    app.config['MAIL_PORT'] = 1025
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USERNAME'] = None
    app.config['MAIL_PASSWORD'] = None
    
    # File upload settings
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
    
    # Session timeout
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    
    # Rate limiting
    app.config['RATELIMIT_STORAGE_URL'] = 'memory://'
    
    # Create upload directories if they don't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'eye_scans'), exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    qrcode.init_app(app)
    limiter.init_app(app)
    
    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from sns_mail.database.models import User
        return User.query.get(int(user_id))
    
    # Custom Jinja2 filters
    @app.template_filter('from_json')
    def from_json_filter(value):
        """Parse a JSON string and return a Python object"""
        if not value:
            return []
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value  # Already parsed
        except (json.JSONDecodeError, TypeError):
            return []
    
    @app.template_filter('to_json')
    def to_json_filter(value):
        """Convert a Python object to a JSON string"""
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return '[]'
    
    # Import and register blueprints
    from sns_mail.core.auth_routes import auth
    from sns_mail.core.client_routes import client
    from sns_mail.core.admin_routes import admin
    from sns_mail.core.server_routes import server
    from sns_mail.core.api_routes import api
    from sns_mail.core.features_routes import features
    
    app.register_blueprint(auth)
    app.register_blueprint(client)
    app.register_blueprint(admin)
    app.register_blueprint(server)
    app.register_blueprint(api)
    app.register_blueprint(features, url_prefix='/features')
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Initialize and start the background scheduler
    from sns_mail.utils.scheduler import scheduler
    scheduler.init_app(app)
    scheduler.start()
    
    # Initialize Context Memory Engine
    from sns_mail.utils.context_memory_engine import context_engine
    context_engine.init_app(app)
    
    # Register shutdown handler
    def shutdown_scheduler():
        scheduler.stop()
    
    atexit.register(shutdown_scheduler)
    
    return app
