#!/usr/bin/env python3
"""
Migration script to add Calendar and Event models to the database.
Run this script to create the necessary tables for the calendar feature.
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sns_mail import create_app, db
from sns_mail.database.models import CalendarEvent, EventAttendee, EventNotification

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Creating calendar tables...")
        
        # Create tables
        try:
            db.create_all()
            print("✓ Calendar tables created successfully!")
            print("  - calendar_events")
            print("  - event_attendees")
            print("  - event_notifications")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            return False
        
        print("\nMigration completed successfully!")
        return True

if __name__ == '__main__':
    migrate()