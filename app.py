#!/usr/bin/env python3
"""
SNS Mail Application Entry Point

This is the main entry point for the SNS Mail web application.
It creates the Flask app, initializes the database, and starts the server.
"""

import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sns_mail import create_app, db, login_manager
from sns_mail.database.models import User, Email, Draft, SecurityLog, VirusScanLog
from sns_mail.config import config

# Create the Flask application
app = create_app()

# Initialize Flask-Migrate for database migrations
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell"""
    return {
        'db': db, 
        'User': User, 
        'Email': Email, 
        'Draft': Draft,
        'SecurityLog': SecurityLog,
        'VirusScanLog': VirusScanLog
    }

@app.cli.command()
def init_db():
    """Initialize the database with tables and sample data"""
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Create default admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                name='System Administrator',
                username='admin',
                email='admin@snsx.com',
                password='Admin123!'
            )
            admin_user.is_admin = True
            admin_user.is_server_admin = True
            db.session.add(admin_user)
            db.session.commit()
            print(f"Created admin user: {admin_user.username}")
        
        # Create sample regular user if it doesn't exist
        sample_user = User.query.filter_by(username='user1').first()
        if not sample_user:
            sample_user = User(
                name='Sample User',
                username='user1',
                email='user1@snsx.com',
                password='User123!'
            )
            db.session.add(sample_user)
            db.session.commit()
            print(f"Created sample user: {sample_user.username}")
        
        print("Database initialized successfully!")

@app.cli.command()
def seed_data():
    """Seed the database with sample data"""
    with app.app_context():
        # Create some sample emails
        admin_user = User.query.filter_by(username='admin').first()
        sample_user = User.query.filter_by(username='user1').first()
        
        if admin_user and sample_user:
            # Sample email from admin to user
            email1 = Email(
                subject='Welcome to SNS Mail!',
                body='Welcome to the SNS Mail platform. Your account has been created successfully.',
                sender_id=admin_user.id,
                recipient_id=sample_user.id
            )
            
            # Sample email from user to admin
            email2 = Email(
                subject='Test Email',
                body='This is a test email to verify the system is working.',
                sender_id=sample_user.id,
                recipient_id=admin_user.id
            )
            
            db.session.add_all([email1, email2])
            db.session.commit()
            
            print("Sample data created successfully!")

@app.cli.command()
def reset_db():
    """Reset the database (drop and recreate)"""
    with app.app_context():
        # Drop all tables
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        print("Database reset successfully!")

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file upload size errors"""
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

if __name__ == '__main__':
    # Get configuration mode
    config_mode = os.environ.get('FLASK_ENV', 'development')
    
    # Run the application on a different port to avoid conflicts
    app.run(
        host='127.0.0.1',
        port=8080,
        debug=config_mode == 'development'
    )
