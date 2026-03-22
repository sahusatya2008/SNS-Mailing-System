"""
Migration script for Context Memory Across Threads feature
Run this script to add the new database tables
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from sns_mail import db
from sns_mail.database.models import (
    ContextMemory, ContextSummary, ContextPhrase, ContextFeedbackLog
)
from sns_mail.utils.context_memory_engine import context_engine

def migrate():
    """Run the migration"""
    with app.app_context():
        print("Starting Context Memory migration...")
        
        # Create new tables
        try:
            print("Creating context_memories table...")
            db.create_all()
            print("✓ All tables created successfully")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            return False
        
        # Initialize default phrases
        try:
            print("Initializing default context phrases...")
            context_engine.init_app(app)
            print("✓ Default phrases initialized")
        except Exception as e:
            print(f"✗ Error initializing phrases: {e}")
            # Continue anyway - phrases might already exist
        
        # Verify tables exist
        try:
            print("\nVerifying tables...")
            
            # Check ContextMemory
            count = ContextMemory.query.count()
            print(f"✓ context_memories table ready (current records: {count})")
            
            # Check ContextSummary
            count = ContextSummary.query.count()
            print(f"✓ context_summaries table ready (current records: {count})")
            
            # Check ContextPhrase
            count = ContextPhrase.query.count()
            print(f"✓ context_phrases table ready (current records: {count})")
            
            # Check ContextFeedbackLog
            count = ContextFeedbackLog.query.count()
            print(f"✓ context_feedback_logs table ready (current records: {count})")
            
        except Exception as e:
            print(f"✗ Error verifying tables: {e}")
            return False
        
        print("\n" + "="*50)
        print("Migration completed successfully!")
        print("="*50)
        print("\nNew tables added:")
        print("  - context_memories")
        print("  - context_summaries")
        print("  - context_phrases")
        print("  - context_feedback_logs")
        print("\nNew API endpoints:")
        print("  - GET  /api/email/<id>/context")
        print("  - POST /api/email/<id>/analyze-context")
        print("  - POST /api/context/<id>/feedback")
        print("  - GET  /api/context/<id>/summary")
        print("  - GET  /api/context-phrases")
        print("  - POST /api/context-phrases")
        print("  - GET  /api/context-stats")
        print("  - GET  /api/context-feedback-logs")
        
        return True

if __name__ == "__main__":
    migrate()