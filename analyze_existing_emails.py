#!/usr/bin/env python3
"""
Script to analyze existing emails for sentiment
Run this to populate sentiment data for all existing emails
"""

import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sns_mail import create_app, db
from sns_mail.database.models import Email, User, SentimentAnalysis, MoodLog
from sns_mail.utils.sentiment_engine import track_user_mood, analyze_content
from datetime import datetime

def analyze_existing_emails():
    """Analyze all existing emails for sentiment"""
    app = create_app()
    
    with app.app_context():
        print("Starting sentiment analysis of existing emails...")
        
        # Get all users
        users = User.query.all()
        
        for user in users:
            print(f"\nAnalyzing emails for user: {user.username}")
            
            # Get emails sent by this user
            sent_emails = Email.query.filter_by(sender_id=user.id).all()
            print(f"  Found {len(sent_emails)} sent emails")
            
            # Get emails received by this user
            received_emails = Email.query.filter_by(recipient_id=user.id).all()
            print(f"  Found {len(received_emails)} received emails")
            
            tracker = track_user_mood(user.id)
            
            # Analyze sent emails
            for email in sent_emails:
                # Check if already analyzed
                existing = SentimentAnalysis.query.filter_by(
                    email_id=email.id, 
                    user_id=user.id
                ).first()
                
                if not existing:
                    try:
                        tracker.analyze_email(email)
                        print(f"    ✓ Analyzed sent email: {email.subject[:30]}...")
                    except Exception as e:
                        print(f"    ✗ Failed to analyze email {email.id}: {e}")
                else:
                    print(f"    - Skipping already analyzed email: {email.subject[:30]}...")
            
            # Analyze received emails
            for email in received_emails:
                # Check if already analyzed
                existing = SentimentAnalysis.query.filter_by(
                    email_id=email.id, 
                    user_id=user.id
                ).first()
                
                if not existing:
                    try:
                        tracker.analyze_email(email)
                        print(f"    ✓ Analyzed received email: {email.subject[:30]}...")
                    except Exception as e:
                        print(f"    ✗ Failed to analyze email {email.id}: {e}")
        
        print("\n" + "="*50)
        print("Sentiment analysis complete!")
        
        # Print summary
        total_analyses = SentimentAnalysis.query.count()
        print(f"Total sentiment analyses: {total_analyses}")

if __name__ == '__main__':
    analyze_existing_emails()