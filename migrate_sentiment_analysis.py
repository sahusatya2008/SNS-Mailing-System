"""
Migration script to add sentiment analysis tables
Run this script to create the new tables for AI sentiment analysis
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from sns_mail import db
from sns_mail.database.models import (
    SentimentAnalysis, MoodInsight, CommunicationPattern
)

def migrate():
    """Create the new sentiment analysis tables"""
    with app.app_context():
        print("Creating sentiment analysis tables...")
        
        # Create tables
        db.create_all()
        
        print("✅ SentimentAnalysis table created")
        print("✅ MoodInsight table created")
        print("✅ CommunicationPattern table created")
        
        print("\nMigration completed successfully!")

if __name__ == '__main__':
    migrate()