"""
Context Memory Across Threads Engine
Intelligent system for detecting and linking related email conversations
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from flask import current_app
from ..database.models import (
    db, Email, User, ContextMemory, ContextSummary, 
    ContextPhrase, ContextFeedbackLog, Task
)
import threading


class ContextMemoryEngine:
    """Main engine for context memory detection and management"""
    
    # Default context detection phrases
    DEFAULT_PHRASES = {
        'reference': [
            'as discussed earlier',
            'as mentioned before',
            'as we discussed',
            'following up on',
            'following up with',
            'regarding our last conversation',
            'regarding our previous discussion',
            'in reference to our earlier',
            'as per our previous',
            'continuing from our last',
            'picking up from where we left',
            'getting back to you on',
            'as promised',
            'as agreed',
            'further to our discussion',
            'in continuation of',
            'reverting back to',
            'as I mentioned earlier',
            'like we talked about',
            'per our conversation',
            'as discussed previously',
            'following our call',
            'following our meeting',
            'as noted earlier',
            'referencing our previous',
            'going back to our discussion',
            'to follow up on',
            'this is regarding',
            'in response to your previous',
            'building on our last conversation'
        ],
        'followup': [
            'just checking in',
            'checking in on',
            'any update on',
            'any updates on',
            'following up',
            'just wanted to follow up',
            'gentle reminder',
            'friendly reminder',
            'just a reminder',
            'circling back',
            'looping back',
            'bumping this up',
            'wanted to check',
            'wanted to follow up',
            'any news on',
            'have you had a chance',
            'have you had time',
            'still waiting for',
            'pending from our last',
            'as a follow-up'
        ],
        'continuation': [
            'continuing from',
            'further to',
            'additionally regarding',
            'more on',
            'adding to our discussion',
            'further information on',
            'additional details on',
            'to continue our discussion',
            'extending our conversation',
            'building upon'
        ]
    }
    
    # Weight configuration for relevance scoring
    WEIGHTS = {
        'semantic_similarity': 0.30,
        'recency': 0.20,
        'participant_overlap': 0.25,
        'subject_alignment': 0.15,
        'action_item': 0.10
    }
    
    # Confidence thresholds
    CONFIDENCE_THRESHOLDS = {
        'high': 0.75,
        'medium': 0.50,
        'low': 0.25
    }
    
    def __init__(self, app=None):
        self.app = app
        self._initialized = False
        
    def init_app(self, app):
        self.app = app
        self._initialize_default_phrases()
        self._initialized = True
        
    def _initialize_default_phrases(self):
        """Initialize default context detection phrases in database"""
        with self.app.app_context():
            for phrase_type, phrases in self.DEFAULT_PHRASES.items():
                for phrase in phrases:
                    existing = ContextPhrase.query.filter_by(phrase=phrase.lower()).first()
                    if not existing:
                        context_phrase = ContextPhrase(
                            phrase=phrase.lower(),
                            phrase_type=phrase_type,
                            weight=1.0,
                            is_active=True
                        )
                        db.session.add(context_phrase)
            try:
                db.session.commit()
            except:
                db.session.rollback()
    
    def detect_context_phrases(self, text: str) -> List[Dict]:
        """Detect context reference phrases in email text"""
        if not text:
            return []
            
        text_lower = text.lower()
        detected = []
        
        # Get all active phrases from database
        phrases = ContextPhrase.query.filter_by(is_active=True).all()
        
        for phrase_obj in phrases:
            if phrase_obj.phrase in text_lower:
                detected.append({
                    'phrase': phrase_obj.phrase,
                    'type': phrase_obj.phrase_type,
                    'weight': phrase_obj.weight,
                    'position': text_lower.find(phrase_obj.phrase)
                })
        
        return detected
    
    def calculate_semantic_similarity(self, email1: Email, email2: Email) -> float:
        """Calculate semantic similarity between two emails"""
        # Simple text-based similarity (can be enhanced with NLP/ML)
        text1 = f"{email1.subject} {email1.body}".lower()
        text2 = f"{email2.subject} {email2.body}".lower()
        
        # Tokenize
        words1 = set(re.findall(r'\b\w+\b', text1))
        words2 = set(re.findall(r'\b\w+\b', text2))
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                      'through', 'during', 'before', 'after', 'above', 'below',
                      'between', 'under', 'again', 'further', 'then', 'once',
                      'here', 'there', 'when', 'where', 'why', 'how', 'all',
                      'each', 'few', 'more', 'most', 'other', 'some', 'such',
                      'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
                      'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
                      'until', 'while', 'this', 'that', 'these', 'those', 'i',
                      'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
                      'who', 'whom', 'your', 'my', 'his', 'her', 'its', 'our',
                      'their', 'me', 'him', 'us', 'them', 'am', 'about', 'any'}
        
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_recency_score(self, email: Email) -> float:
        """Calculate recency score (more recent = higher score)"""
        now = datetime.utcnow()
        email_time = email.sent_at
        
        # Score decays over time
        days_diff = (now - email_time).days
        
        if days_diff <= 1:
            return 1.0
        elif days_diff <= 7:
            return 0.9 - (days_diff * 0.05)
        elif days_diff <= 30:
            return 0.55 - ((days_diff - 7) * 0.01)
        elif days_diff <= 90:
            return 0.27 - ((days_diff - 30) * 0.002)
        else:
            return max(0.1, 0.07 - ((days_diff - 90) * 0.0005))
    
    def calculate_participant_overlap(self, email1: Email, email2: Email) -> float:
        """Calculate participant overlap score"""
        participants1 = {email1.sender_id, email1.recipient_id}
        participants2 = {email2.sender_id, email2.recipient_id}
        
        intersection = len(participants1 & participants2)
        union = len(participants1 | participants2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_subject_alignment(self, email1: Email, email2: Email) -> float:
        """Calculate subject line alignment score"""
        subject1 = email1.subject.lower()
        subject2 = email2.subject.lower()
        
        # Remove common prefixes
        prefixes = ['re:', 'fwd:', 'fw:', 'reply:', 'forward:']
        for prefix in prefixes:
            if subject1.startswith(prefix):
                subject1 = subject1[len(prefix):].strip()
            if subject2.startswith(prefix):
                subject2 = subject2[len(prefix):].strip()
        
        # Tokenize
        words1 = set(re.findall(r'\b\w+\b', subject1))
        words2 = set(re.findall(r'\b\w+\b', subject2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        # Bonus for exact match after prefix removal
        if subject1 == subject2:
            return 1.0
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_action_item_score(self, email: Email) -> float:
        """Calculate if email contains action items or pending tasks"""
        action_keywords = [
            'action', 'todo', 'task', 'pending', 'waiting for', 'need to',
            'please', 'required', 'deadline', 'due', 'follow up', 'follow-up',
            'reminder', 'urgent', 'asap', 'as soon as possible', 'by tomorrow',
            'by next', 'complete', 'finish', 'submit', 'review', 'approve',
            'confirm', 'respond', 'reply', 'get back', 'let me know'
        ]
        
        text = f"{email.subject} {email.body}".lower()
        score = 0.0
        
        for keyword in action_keywords:
            if keyword in text:
                score += 0.1
        
        # Check if there's an actual task linked
        task = Task.query.filter_by(email_id=email.id).first()
        if task and task.status != 'completed':
            score += 0.3
        
        return min(1.0, score)
    
    def calculate_overall_confidence(self, scores: Dict) -> Tuple[float, str]:
        """Calculate weighted overall confidence score"""
        overall = (
            scores['semantic_similarity'] * self.WEIGHTS['semantic_similarity'] +
            scores['recency'] * self.WEIGHTS['recency'] +
            scores['participant_overlap'] * self.WEIGHTS['participant_overlap'] +
            scores['subject_alignment'] * self.WEIGHTS['subject_alignment'] +
            scores['action_item'] * self.WEIGHTS['action_item']
        )
        
        # Determine confidence level
        if overall >= self.CONFIDENCE_THRESHOLDS['high']:
            level = 'high'
        elif overall >= self.CONFIDENCE_THRESHOLDS['medium']:
            level = 'medium'
        else:
            level = 'low'
        
        return overall, level
    
    def find_related_emails(self, email: Email, user_id: int, limit: int = 5) -> List[Dict]:
        """Find related emails for a given email"""
        # Get user's emails (sent or received)
        user_emails = Email.query.filter(
            db.or_(
                Email.sender_id == user_id,
                Email.recipient_id == user_id
            ),
            Email.id != email.id,
            Email.is_deleted == False,
            Email.is_spam == False
        ).order_by(Email.sent_at.desc()).limit(100).all()
        
        results = []
        
        for candidate in user_emails:
            # Calculate all scores
            scores = {
                'semantic_similarity': self.calculate_semantic_similarity(email, candidate),
                'recency': self.calculate_recency_score(candidate),
                'participant_overlap': self.calculate_participant_overlap(email, candidate),
                'subject_alignment': self.calculate_subject_alignment(email, candidate),
                'action_item': self.calculate_action_item_score(candidate)
            }
            
            overall, level = self.calculate_overall_confidence(scores)
            
            # Only include if above minimum threshold
            if overall >= self.CONFIDENCE_THRESHOLDS['low']:
                results.append({
                    'email': candidate,
                    'scores': scores,
                    'overall_confidence': overall,
                    'confidence_level': level
                })
        
        # Sort by overall confidence
        results.sort(key=lambda x: x['overall_confidence'], reverse=True)
        
        return results[:limit]
    
    def analyze_email_async(self, email_id: int, user_id: int):
        """Asynchronously analyze an email for context"""
        def _analyze():
            with self.app.app_context():
                try:
                    email = Email.query.get(email_id)
                    if not email:
                        return
                    
                    # Detect context phrases
                    detected_phrases = self.detect_context_phrases(
                        f"{email.subject} {email.body}"
                    )
                    
                    # Only proceed if context phrases detected or this is a reply
                    if not detected_phrases and 're:' not in email.subject.lower():
                        return
                    
                    # Find related emails
                    related = self.find_related_emails(email, user_id)
                    
                    # Store context memories
                    for rel in related:
                        # Check if already exists
                        existing = ContextMemory.query.filter_by(
                            user_id=user_id,
                            current_email_id=email.id,
                            related_email_id=rel['email'].id
                        ).first()
                        
                        if existing:
                            # Update existing
                            existing.semantic_similarity_score = rel['scores']['semantic_similarity']
                            existing.recency_score = rel['scores']['recency']
                            existing.participant_overlap_score = rel['scores']['participant_overlap']
                            existing.subject_alignment_score = rel['scores']['subject_alignment']
                            existing.action_item_score = rel['scores']['action_item']
                            existing.overall_confidence = rel['overall_confidence']
                            existing.confidence_level = rel['confidence_level']
                            existing.detected_phrases = json.dumps(detected_phrases)
                            existing.updated_at = datetime.utcnow()
                        else:
                            # Create new
                            context = ContextMemory(
                                user_id=user_id,
                                current_email_id=email.id,
                                related_email_id=rel['email'].id,
                                semantic_similarity_score=rel['scores']['semantic_similarity'],
                                recency_score=rel['scores']['recency'],
                                participant_overlap_score=rel['scores']['participant_overlap'],
                                subject_alignment_score=rel['scores']['subject_alignment'],
                                action_item_score=rel['scores']['action_item'],
                                overall_confidence=rel['overall_confidence'],
                                confidence_level=rel['confidence_level'],
                                detected_phrases=json.dumps(detected_phrases),
                                detection_method='auto'
                            )
                            db.session.add(context)
                    
                    db.session.commit()
                    
                    # Generate summaries for high-confidence matches
                    for rel in related:
                        if rel['confidence_level'] == 'high':
                            self._generate_summary(rel['email'], user_id)
                            
                except Exception as e:
                    print(f"Error in context analysis: {e}")
                    db.session.rollback()
        
        # Run in background thread
        thread = threading.Thread(target=_analyze)
        thread.daemon = True
        thread.start()
    
    def _generate_summary(self, email: Email, user_id: int):
        """Generate a structured summary for an email thread"""
        # Check if summary already exists
        existing = ContextSummary.query.filter_by(
            user_id=user_id,
            email_id=email.id
        ).first()
        
        # Extract key information
        key_decisions = self._extract_decisions(email.body)
        pending_tasks = self._extract_pending_tasks(email)
        key_points = self._extract_key_points(email.body)
        
        # Generate summary text
        summary_text = self._generate_summary_text(
            email, key_decisions, pending_tasks, key_points
        )
        
        if existing:
            existing.key_decisions = json.dumps(key_decisions)
            existing.pending_tasks = json.dumps(pending_tasks)
            existing.key_points = json.dumps(key_points)
            existing.summary_text = summary_text
            existing.updated_at = datetime.utcnow()
        else:
            summary = ContextSummary(
                user_id=user_id,
                email_id=email.id,
                key_decisions=json.dumps(key_decisions),
                pending_tasks=json.dumps(pending_tasks),
                key_points=json.dumps(key_points),
                summary_text=summary_text,
                last_status=email.body[:200] + '...' if len(email.body) > 200 else email.body
            )
            db.session.add(summary)
        
        db.session.commit()
    
    def _extract_decisions(self, text: str) -> List[str]:
        """Extract decisions from email text"""
        decisions = []
        decision_patterns = [
            r'(?:decided|agreed|confirmed|approved)\s+(?:that\s+)?(.+?)(?:\.|!|\n)',
            r'(?:decision|agreement):\s*(.+?)(?:\.|!|\n)',
            r'we\s+will\s+(.+?)(?:\.|!|\n)',
            r'(?:finalized|settled on)\s+(.+?)(?:\.|!|\n)'
        ]
        
        for pattern in decision_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            decisions.extend([m.strip() for m in matches if m.strip()])
        
        return decisions[:5]  # Limit to 5 decisions
    
    def _extract_pending_tasks(self, email: Email) -> List[Dict]:
        """Extract pending tasks from email"""
        tasks = []
        
        # Check for linked tasks
        linked_tasks = Task.query.filter_by(email_id=email.id).all()
        for task in linked_tasks:
            if task.status != 'completed':
                tasks.append({
                    'title': task.title,
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                    'priority': task.priority,
                    'status': task.status
                })
        
        # Extract from text
        text = email.body
        task_patterns = [
            r'(?:todo|task|action item):\s*(.+?)(?:\.|!|\n)',
            r'(?:need to|please)\s+(.+?)(?:\.|!|\n)',
            r'(?:waiting for|pending)\s+(.+?)(?:\.|!|\n)'
        ]
        
        for pattern in task_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if m.strip() and len(tasks) < 5:
                    tasks.append({
                        'title': m.strip(),
                        'source': 'extracted'
                    })
        
        return tasks[:5]
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key discussion points"""
        points = []
        
        # Look for bullet points or numbered lists
        bullet_pattern = r'[-•*]\s*(.+?)(?:\n|$)'
        numbered_pattern = r'\d+[.)]\s*(.+?)(?:\n|$)'
        
        bullets = re.findall(bullet_pattern, text)
        numbered = re.findall(numbered_pattern, text)
        
        points.extend([b.strip() for b in bullets if b.strip()])
        points.extend([n.strip() for n in numbered if n.strip()])
        
        # If no lists found, extract sentences with key phrases
        if not points:
            key_phrases = ['important', 'key', 'main', 'critical', 'essential', 'note that']
            sentences = text.split('.')
            for sentence in sentences:
                for phrase in key_phrases:
                    if phrase in sentence.lower():
                        points.append(sentence.strip())
                        break
        
        return points[:5]
    
    def _generate_summary_text(self, email: Email, decisions: List, 
                                tasks: List, points: List) -> str:
        """Generate human-readable summary"""
        parts = []
        
        parts.append(f"Subject: {email.subject}")
        parts.append(f"Date: {email.sent_at.strftime('%Y-%m-%d %H:%M')}")
        parts.append(f"From: {email.sender.name}")
        parts.append("")
        
        if decisions:
            parts.append("Key Decisions:")
            for i, d in enumerate(decisions, 1):
                parts.append(f"  {i}. {d}")
            parts.append("")
        
        if tasks:
            parts.append("Pending Tasks:")
            for i, t in enumerate(tasks, 1):
                parts.append(f"  {i}. {t['title']}")
            parts.append("")
        
        if points:
            parts.append("Key Points:")
            for i, p in enumerate(points, 1):
                parts.append(f"  {i}. {p}")
        
        return "\n".join(parts)
    
    def get_context_for_email(self, email_id: int, user_id: int) -> Dict:
        """Get context memory data for an email"""
        memories = ContextMemory.query.filter_by(
            user_id=user_id,
            current_email_id=email_id,
            is_active=True
        ).order_by(ContextMemory.overall_confidence.desc()).all()
        
        if not memories:
            return {
                'has_context': False,
                'message': 'No related prior discussions detected',
                'contexts': []
            }
        
        contexts = []
        for memory in memories:
            related_email = memory.related_email
            summary = ContextSummary.query.filter_by(
                email_id=related_email.id,
                user_id=user_id
            ).first()
            
            context_data = {
                'memory_id': memory.id,
                'email_id': related_email.id,
                'subject': related_email.subject,
                'sender': related_email.sender.name,
                'date': related_email.sent_at.strftime('%Y-%m-%d %H:%M'),
                'confidence': memory.overall_confidence,
                'confidence_level': memory.confidence_level,
                'detected_phrases': json.loads(memory.detected_phrases) if memory.detected_phrases else [],
                'preview': related_email.body[:150] + '...' if len(related_email.body) > 150 else related_email.body,
                'summary': summary.summary_text if summary else None,
                'key_decisions': json.loads(summary.key_decisions) if summary and summary.key_decisions else [],
                'pending_tasks': json.loads(summary.pending_tasks) if summary and summary.pending_tasks else [],
                'user_feedback': memory.user_feedback
            }
            contexts.append(context_data)
        
        return {
            'has_context': True,
            'total_found': len(contexts),
            'contexts': contexts
        }
    
    def record_feedback(self, memory_id: int, user_id: int, 
                        feedback: str) -> bool:
        """Record user feedback on a context link"""
        memory = ContextMemory.query.filter_by(
            id=memory_id,
            user_id=user_id
        ).first()
        
        if not memory:
            return False
        
        # Update memory
        original_confidence = memory.overall_confidence
        memory.user_feedback = feedback
        memory.feedback_at = datetime.utcnow()
        
        # Adjust confidence based on feedback
        if feedback == 'relevant':
            memory.overall_confidence = min(1.0, memory.overall_confidence + 0.1)
        elif feedback == 'not_relevant':
            memory.overall_confidence = max(0.0, memory.overall_confidence - 0.2)
            if memory.overall_confidence < self.CONFIDENCE_THRESHOLDS['low']:
                memory.is_active = False
        
        # Update confidence level
        if memory.overall_confidence >= self.CONFIDENCE_THRESHOLDS['high']:
            memory.confidence_level = 'high'
        elif memory.overall_confidence >= self.CONFIDENCE_THRESHOLDS['medium']:
            memory.confidence_level = 'medium'
        else:
            memory.confidence_level = 'low'
        
        # Log feedback for learning
        feedback_log = ContextFeedbackLog(
            user_id=user_id,
            context_memory_id=memory_id,
            feedback_type=feedback,
            original_confidence=original_confidence,
            adjusted_confidence=memory.overall_confidence,
            features_snapshot=json.dumps({
                'semantic_similarity': memory.semantic_similarity_score,
                'recency': memory.recency_score,
                'participant_overlap': memory.participant_overlap_score,
                'subject_alignment': memory.subject_alignment_score,
                'action_item': memory.action_item_score
            })
        )
        db.session.add(feedback_log)
        db.session.commit()
        
        return True
    
    def analyze_email_sync(self, email_id: int, user_id: int) -> Dict:
        """Synchronously analyze an email and return results"""
        email = Email.query.get(email_id)
        if not email:
            return {'error': 'Email not found'}
        
        # Detect context phrases
        detected_phrases = self.detect_context_phrases(
            f"{email.subject} {email.body}"
        )
        
        # Find related emails
        related = self.find_related_emails(email, user_id)
        
        # Store context memories
        for rel in related:
            existing = ContextMemory.query.filter_by(
                user_id=user_id,
                current_email_id=email.id,
                related_email_id=rel['email'].id
            ).first()
            
            if not existing:
                context = ContextMemory(
                    user_id=user_id,
                    current_email_id=email.id,
                    related_email_id=rel['email'].id,
                    semantic_similarity_score=rel['scores']['semantic_similarity'],
                    recency_score=rel['scores']['recency'],
                    participant_overlap_score=rel['scores']['participant_overlap'],
                    subject_alignment_score=rel['scores']['subject_alignment'],
                    action_item_score=rel['scores']['action_item'],
                    overall_confidence=rel['overall_confidence'],
                    confidence_level=rel['confidence_level'],
                    detected_phrases=json.dumps(detected_phrases),
                    detection_method='auto'
                )
                db.session.add(context)
        
        db.session.commit()
        
        return {
            'email_id': email_id,
            'detected_phrases': detected_phrases,
            'related_count': len(related),
            'related_emails': [{
                'id': r['email'].id,
                'subject': r['email'].subject,
                'confidence': r['overall_confidence'],
                'level': r['confidence_level']
            } for r in related]
        }


# Global engine instance
context_engine = ContextMemoryEngine()