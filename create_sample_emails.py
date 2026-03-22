#!/usr/bin/env python3
"""
Script to create sample emails between registered users to demonstrate Context Memory feature.
This creates real emails that reference each other to show thread linking.
"""

from sns_mail import create_app, db
from sns_mail.database.models import User, Email, SentFolder
from datetime import datetime, timedelta
import random

def create_sample_emails():
    app = create_app()
    with app.app_context():
        # Get users
        test = User.query.filter_by(username='test').first()
        test1 = User.query.filter_by(username='test1').first()
        admin = User.query.filter_by(username='admin').first()
        
        if not all([test, test1, admin]):
            print("Error: Not all users found!")
            return
        
        print(f"Creating sample emails between users:")
        print(f"  - {test.username} ({test.email})")
        print(f"  - {test1.username} ({test1.email})")
        print(f"  - {admin.username} ({admin.email})")
        print()
        
        # Email thread 1: Project Discussion between test and test1
        emails_data = [
            # Thread 1: Project Alpha Discussion
            {
                'sender': test,
                'recipient': test1,
                'subject': 'Project Alpha - Initial Discussion',
                'body': '''Hi test1,

I wanted to reach out to discuss Project Alpha. I think we have a great opportunity to collaborate on this.

Key points I'd like to discuss:
1. Timeline and milestones
2. Resource allocation
3. Budget considerations

Let me know your thoughts on this.

Best regards,
test''',
                'hours_ago': 48
            },
            {
                'sender': test1,
                'recipient': test,
                'subject': 'Re: Project Alpha - Initial Discussion',
                'body': '''Hi test,

Thanks for reaching out! I'm excited about Project Alpha.

As discussed earlier, I think we should focus on the timeline first. Here's my proposed schedule:
- Phase 1: 2 weeks
- Phase 2: 3 weeks
- Phase 3: 2 weeks

Let's schedule a call to discuss the details.

Best,
test1''',
                'hours_ago': 44
            },
            {
                'sender': test,
                'recipient': test1,
                'subject': 'Project Alpha - Timeline Update',
                'body': '''Hi test1,

Following up on our conversation about Project Alpha, I've reviewed the timeline you proposed.

I think the schedule looks good overall. However, I have a few suggestions:
- Phase 1 could be extended to 3 weeks for better testing
- Phase 2 seems reasonable at 3 weeks
- Phase 3 might need an extra week for final polish

As we discussed earlier, let's prioritize quality over speed.

What do you think?

Best,
test''',
                'hours_ago': 36
            },
            {
                'sender': test1,
                'recipient': test,
                'subject': 'Re: Project Alpha - Timeline Update',
                'body': '''Hi test,

I agree with your suggestions regarding the timeline. As discussed in our previous conversation, quality is indeed our top priority.

Let's finalize the schedule:
- Phase 1: 3 weeks (including testing)
- Phase 2: 3 weeks
- Phase 3: 3 weeks (with buffer)

I'll prepare the detailed project plan and share it with you tomorrow.

Best regards,
test1''',
                'hours_ago': 30
            },
            
            # Thread 2: Meeting Request between admin and test
            {
                'sender': admin,
                'recipient': test,
                'subject': 'Quarterly Review Meeting',
                'body': '''Hello test,

I hope this email finds you well. I'd like to schedule a quarterly review meeting to discuss your team's progress.

Please let me know your availability for next week.

Best regards,
Admin''',
                'hours_ago': 24
            },
            {
                'sender': test,
                'recipient': admin,
                'subject': 'Re: Quarterly Review Meeting',
                'body': '''Hi Admin,

Thank you for reaching out. Regarding our last discussion about quarterly reviews, I'm available on:
- Tuesday: 2 PM - 4 PM
- Thursday: 10 AM - 12 PM
- Friday: 3 PM - 5 PM

Please let me know which slot works best for you.

Best,
test''',
                'hours_ago': 20
            },
            {
                'sender': admin,
                'recipient': test,
                'subject': 'Re: Quarterly Review Meeting - Confirmed',
                'body': '''Hi test,

Following up on our conversation, I've scheduled our meeting for Tuesday at 2 PM.

As discussed earlier, please prepare the following:
1. Team performance metrics
2. Project status updates
3. Resource requirements for next quarter

Looking forward to our discussion.

Best regards,
Admin''',
                'hours_ago': 16
            },
            
            # Thread 3: Technical Discussion between test1 and admin
            {
                'sender': test1,
                'recipient': admin,
                'subject': 'System Upgrade Proposal',
                'body': '''Hello Admin,

I wanted to discuss a potential system upgrade that could significantly improve our infrastructure.

Key proposals:
1. Database optimization
2. Server scaling
3. Security enhancements

I've attached a detailed proposal document for your review.

Best regards,
test1''',
                'hours_ago': 12
            },
            {
                'sender': admin,
                'recipient': test1,
                'subject': 'Re: System Upgrade Proposal',
                'body': '''Hi test1,

Thank you for the detailed proposal. As we discussed previously about infrastructure improvements, this aligns well with our goals.

I have a few questions:
1. What's the estimated timeline for implementation?
2. What resources would be required?
3. What's the expected ROI?

Let's schedule a technical review meeting to discuss further.

Best,
Admin''',
                'hours_ago': 8
            },
            {
                'sender': test1,
                'recipient': admin,
                'subject': 'Re: System Upgrade Proposal - Details',
                'body': '''Hi Admin,

Following up on our conversation about the system upgrade, here are the details you requested:

Timeline: 6-8 weeks
Resources: 2 developers, 1 DevOps engineer
Expected ROI: 40% performance improvement, 25% cost reduction

As discussed earlier, I recommend we start with the database optimization phase first.

Shall I proceed with creating a detailed implementation plan?

Best regards,
test1''',
                'hours_ago': 4
            },
            
            # Thread 4: Collaboration between test and test1
            {
                'sender': test1,
                'recipient': test,
                'subject': 'Documentation Review Request',
                'body': '''Hi test,

I've completed the documentation for the new feature we discussed last week.

Could you please review it when you get a chance? I'd appreciate your feedback on:
1. Technical accuracy
2. Clarity of explanations
3. Completeness of examples

Thanks!
test1''',
                'hours_ago': 6
            },
            {
                'sender': test,
                'recipient': test1,
                'subject': 'Re: Documentation Review Request',
                'body': '''Hi test1,

I've reviewed the documentation. As we discussed earlier, it's well-structured and comprehensive.

A few minor suggestions:
- Add more code examples in section 3
- Include troubleshooting tips
- Expand the API reference section

Overall, great work! Let me know if you need any clarification on my feedback.

Best,
test''',
                'hours_ago': 2
            },
            
            # Single email to demonstrate context detection
            {
                'sender': test,
                'recipient': test1,
                'subject': 'Weekend Plans',
                'body': '''Hey test1,

Just wanted to check if you're free this weekend? A few of us are planning to get together.

No rush - just let me know when you can.

Cheers,
test''',
                'hours_ago': 1
            }
        ]
        
        created_count = 0
        for email_data in emails_data:
            # Check if email already exists
            existing = Email.query.filter_by(
                subject=email_data['subject'],
                sender_id=email_data['sender'].id,
                recipient_id=email_data['recipient'].id
            ).first()
            
            if existing:
                print(f"  Skipping (exists): {email_data['subject']}")
                continue
            
            # Create email
            sent_time = datetime.utcnow() - timedelta(hours=email_data['hours_ago'])
            
            email = Email(
                subject=email_data['subject'],
                body=email_data['body'],
                sender_id=email_data['sender'].id,
                recipient_id=email_data['recipient'].id,
                sent_at=sent_time,
                is_read=random.choice([True, False])  # Randomly mark some as read
            )
            
            db.session.add(email)
            db.session.flush()  # Get the email ID
            
            # Add to sender's sent folder
            sent_folder = SentFolder(
                email_id=email.id,
                user_id=email_data['sender'].id
            )
            db.session.add(sent_folder)
            
            created_count += 1
            print(f"  Created: {email_data['subject']} (from {email_data['sender'].username} to {email_data['recipient'].username})")
        
        db.session.commit()
        print()
        print(f"Successfully created {created_count} sample emails!")
        print()
        print("Email threads created:")
        print("  1. Project Alpha Discussion (test <-> test1) - 4 emails")
        print("  2. Quarterly Review Meeting (admin <-> test) - 3 emails")
        print("  3. System Upgrade Proposal (test1 <-> admin) - 3 emails")
        print("  4. Documentation Review (test1 <-> test) - 2 emails")
        print("  5. Weekend Plans (test -> test1) - 1 email")
        print()
        print("Context Memory phrases to look for:")
        print("  - 'As discussed earlier'")
        print("  - 'Following up on our conversation'")
        print("  - 'As we discussed'")
        print("  - 'Regarding our last discussion'")

if __name__ == '__main__':
    create_sample_emails()