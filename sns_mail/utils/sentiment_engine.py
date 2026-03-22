"""
Advanced AI Sentiment Analysis Engine for SNS Mail
Real-time analysis of emails, notes, tasks, and all communications
Detects tone, mood, emotions, urgency, and provides detailed insights
"""

import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
from flask import current_app
from .. import db


class SentimentAnalyzer:
    """
    Advanced sentiment analysis engine that analyzes text content
    and provides comprehensive emotional insights
    """
    
    # Emotion categories with associated words and weights
    EMOTION_LEXICON = {
        # Positive emotions
        'joy': {
            'words': ['happy', 'glad', 'joy', 'delighted', 'pleased', 'thrilled', 'excited', 
                     'wonderful', 'amazing', 'fantastic', 'great', 'excellent', 'awesome',
                     'fantastic', 'brilliant', 'superb', 'love', 'loved', 'enjoy', 'enjoyed',
                     'celebrate', 'celebration', 'cheerful', 'grateful', 'thankful', 'blessed',
                     'smile', 'smiling', 'laugh', 'laughing', 'happiness', 'joyful', 'elated',
                     'overjoyed', 'ecstatic', 'content', 'satisfied', 'fulfilled', 'proud'],
            'weight': 1.0,
            'category': 'positive'
        },
        'trust': {
            'words': ['trust', 'trusted', 'reliable', 'dependable', 'honest', 'sincere',
                     'genuine', 'authentic', 'faithful', 'loyal', 'confident', 'assurance',
                     'secure', 'safe', 'certain', 'sure', 'believe', 'belief', 'faith',
                     'collaborate', 'collaboration', 'partner', 'partnership', 'together'],
            'weight': 0.9,
            'category': 'positive'
        },
        'anticipation': {
            'words': ['expect', 'expecting', 'anticipate', 'anticipating', 'looking forward',
                     'excited', 'eager', 'ready', 'prepare', 'preparing', 'plan', 'planning',
                     'hope', 'hoping', 'hopeful', 'upcoming', 'soon', 'await', 'awaiting',
                     'future', 'next', 'following', 'scheduled', 'arranged', 'organized'],
            'weight': 0.7,
            'category': 'positive'
        },
        'surprise': {
            'words': ['surprise', 'surprised', 'surprising', 'unexpected', 'sudden', 'shock',
                     'shocked', 'amazing', 'astonishing', 'remarkable', 'incredible', 'wow',
                     'unbelievable', 'extraordinary', 'unprecedented', 'out of blue'],
            'weight': 0.6,
            'category': 'neutral'
        },
        
        # Negative emotions
        'anger': {
            'words': ['angry', 'anger', 'furious', 'mad', 'rage', 'outrage', 'annoyed',
                     'annoying', 'irritated', 'irritating', 'frustrated', 'frustrating',
                     'upset', 'pissed', 'hate', 'hated', 'hostile', 'aggressive', 'violent',
                     'disgusted', 'disgusting', 'offended', 'offensive', 'resentful',
                     'bitter', 'infuriated', 'enraged', 'livid', 'outraged', 'temper',
                     'blame', 'blamed', 'fault', 'guilty', 'unfair', 'injustice'],
            'weight': 1.0,
            'category': 'negative'
        },
        'fear': {
            'words': ['fear', 'afraid', 'scared', 'terrified', 'horror', 'horrified',
                     'anxious', 'anxiety', 'worried', 'worry', 'nervous', 'panic', 'dread',
                     'frightened', 'alarmed', 'threatened', 'danger', 'dangerous', 'risk',
                     'uncertain', 'uncertainty', 'doubt', 'suspicious', 'cautious', 'warning',
                     'crisis', 'emergency', 'critical', 'severe', 'serious', 'concern'],
            'weight': 0.95,
            'category': 'negative'
        },
        'sadness': {
            'words': ['sad', 'sadness', 'unhappy', 'depressed', 'depression', 'miserable',
                     'heartbroken', 'devastated', 'grief', 'grieving', 'sorrow', 'sorrowful',
                     'melancholy', 'despair', 'hopeless', 'disappointed', 'disappointing',
                     'regret', 'regretful', 'lonely', 'alone', 'isolated', 'abandoned',
                     'rejected', 'loss', 'lost', 'miss', 'missing', 'cry', 'crying', 'tears',
                     'painful', 'hurt', 'hurtful', 'wound', 'wounded', 'suffering'],
            'weight': 0.9,
            'category': 'negative'
        },
        'disgust': {
            'words': ['disgust', 'disgusted', 'disgusting', 'repulsed', 'repulsive',
                     'revolting', 'nauseating', 'sickening', 'appalling', 'awful', 'terrible',
                     'horrible', 'dreadful', 'atrocious', 'abominable', 'detest', 'loathe',
                     'despise', 'contempt', 'contemptuous', 'scorn', 'scornful'],
            'weight': 0.85,
            'category': 'negative'
        },
        
        # Professional emotions
        'confidence': {
            'words': ['confident', 'confidence', 'sure', 'certain', 'definite', 'clear',
                     'decisive', 'firm', 'strong', 'capable', 'competent', 'proficient',
                     'expert', 'skilled', 'experienced', 'qualified', 'prepared', 'ready',
                     'assured', 'convinced', 'positive', 'definitely', 'absolutely', 'certainly'],
            'weight': 0.8,
            'category': 'positive'
        },
        'urgency': {
            'words': ['urgent', 'urgently', 'immediate', 'immediately', 'asap', 'emergency',
                     'critical', 'crucial', 'vital', 'essential', 'important', 'priority',
                     'deadline', 'overdue', 'late', 'hurry', 'rush', 'quick', 'quickly',
                     'fast', 'soon', 'now', 'today', 'tonight', 'right away', 'promptly'],
            'weight': 0.75,
            'category': 'neutral'
        },
        'formal': {
            'words': ['sincerely', 'regards', 'respectfully', 'formally', 'official',
                     'hereby', 'pursuant', 'accordance', 'therefore', 'consequently',
                     'furthermore', 'moreover', 'nevertheless', 'notwithstanding',
                     'dear', 'honorable', 'esteemed', 'distinguished'],
            'weight': 0.5,
            'category': 'neutral'
        },
        'gratitude': {
            'words': ['thank', 'thanks', 'thankful', 'grateful', 'gratitude', 'appreciate',
                     'appreciated', 'appreciation', 'indebted', 'obliged', 'recognize',
                     'acknowledge', 'acknowledgment', 'recognition', 'value', 'valued',
                     'welcome', 'pleasure', 'honored', 'privilege'],
            'weight': 0.85,
            'category': 'positive'
        },
        'apology': {
            'words': ['sorry', 'apologize', 'apology', 'apologies', 'regret', 'regrets',
                     'forgive', 'forgiveness', 'pardon', 'excuse', 'mistake', 'error',
                     'fault', 'blame', 'responsible', 'accountable', 'oversight'],
            'weight': 0.6,
            'category': 'neutral'
        }
    }
    
    # Intensifiers and diminishers
    INTENSIFIERS = {
        'very': 1.5, 'extremely': 2.0, 'incredibly': 1.8, 'absolutely': 1.7,
        'really': 1.4, 'so': 1.3, 'totally': 1.6, 'completely': 1.5,
        'highly': 1.4, 'deeply': 1.5, 'truly': 1.4, 'quite': 1.2,
        'especially': 1.3, 'particularly': 1.3, 'remarkably': 1.4
    }
    
    DIMINISHERS = {
        'slightly': 0.6, 'somewhat': 0.7, 'a bit': 0.6, 'a little': 0.6,
        'kind of': 0.7, 'sort of': 0.7, 'fairly': 0.8, 'rather': 0.8,
        'mildly': 0.6, 'partially': 0.7, 'almost': 0.8, 'nearly': 0.8
    }
    
    # Negation words
    NEGATIONS = ['not', "n't", 'never', 'no', 'none', 'neither', 'nobody', 'nothing', 'nowhere']
    
    # Punctuation sentiment modifiers
    PUNCTUATION_WEIGHTS = {
        '!': 1.1, '!!': 1.2, '!!!': 1.3,
        '?': 0.95, '??': 0.9, '???': 0.85,
        '...': 0.9
    }
    
    def __init__(self):
        self._build_word_index()
    
    def _build_word_index(self):
        """Build a reverse index for fast word lookup"""
        self.word_to_emotion = {}
        for emotion, data in self.EMOTION_LEXICON.items():
            for word in data['words']:
                self.word_to_emotion[word.lower()] = {
                    'emotion': emotion,
                    'weight': data['weight'],
                    'category': data['category']
                }
    
    def analyze_text(self, text):
        """
        Comprehensive text analysis
        Returns detailed sentiment and emotion data
        """
        if not text or not isinstance(text, str):
            return self._empty_result()
        
        # Preprocess text
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Initialize results
        emotion_scores = defaultdict(float)
        emotion_counts = defaultdict(int)
        word_sentiments = []
        
        # Track for overall sentiment
        positive_score = 0.0
        negative_score = 0.0
        neutral_score = 0.0
        
        # Analyze each word with context
        negation_active = False
        intensifier = 1.0
        
        for i, word in enumerate(words):
            # Check for negation
            if word in self.NEGATIONS or word.endswith("n't"):
                negation_active = True
                continue
            
            # Check for intensifiers/diminishers
            if word in self.INTENSIFIERS:
                intensifier = self.INTENSIFIERS[word]
                continue
            if word in self.DIMINISHERS:
                intensifier = self.DIMINISHERS[word]
                continue
            
            # Look up emotion
            if word in self.word_to_emotion:
                emotion_data = self.word_to_emotion[word]
                emotion = emotion_data['emotion']
                base_weight = emotion_data['weight']
                category = emotion_data['category']
                
                # Apply modifiers
                final_weight = base_weight * intensifier
                if negation_active:
                    # Negation flips the sentiment
                    if category == 'positive':
                        category = 'negative'
                        final_weight *= 0.7  # Negated positive is less negative
                    elif category == 'negative':
                        category = 'positive'
                        final_weight *= 0.7
                    emotion = f"negated_{emotion}"
                
                emotion_scores[emotion] += final_weight
                emotion_counts[emotion] += 1
                
                word_sentiments.append({
                    'word': word,
                    'emotion': emotion,
                    'category': category,
                    'weight': final_weight
                })
                
                # Update overall scores
                if category == 'positive':
                    positive_score += final_weight
                elif category == 'negative':
                    negative_score += final_weight
                else:
                    neutral_score += final_weight
                
                # Reset modifiers
                negation_active = False
                intensifier = 1.0
        
        # Analyze punctuation
        punctuation_modifier = 1.0
        for punct, weight in self.PUNCTUATION_WEIGHTS.items():
            if punct in text:
                punctuation_modifier *= weight
        
        # Apply punctuation modifier
        positive_score *= punctuation_modifier
        negative_score *= punctuation_modifier
        
        # Calculate overall sentiment score (-1 to 1)
        total_sentiment = positive_score + negative_score + neutral_score
        if total_sentiment > 0:
            sentiment_score = (positive_score - negative_score) / total_sentiment
        else:
            sentiment_score = 0.0
        
        # Clamp to -1 to 1
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        # Determine sentiment label
        if sentiment_score > 0.1:
            sentiment_label = 'positive'
        elif sentiment_score < -0.1:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        # Calculate emotion percentages
        total_emotion = sum(emotion_scores.values()) if emotion_scores else 1
        emotion_percentages = {
            emotion: round((score / total_emotion) * 100, 2)
            for emotion, score in emotion_scores.items()
        }
        
        # Determine dominant emotions
        sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
        dominant_emotions = [e[0] for e in sorted_emotions[:3]]
        
        # Analyze text characteristics
        text_stats = self._analyze_text_statistics(text, words, sentences)
        
        # Detect urgency level
        urgency_level = self._detect_urgency(text, words)
        
        # Detect formality level
        formality_level = self._detect_formality(text, words)
        
        # Generate insights
        insights = self._generate_insights(
            sentiment_score, sentiment_label, dominant_emotions,
            emotion_percentages, urgency_level, formality_level, text_stats
        )
        
        return {
            'sentiment_score': round(sentiment_score, 4),
            'sentiment_label': sentiment_label,
            'confidence': round(self._calculate_confidence(word_sentiments, len(words)), 4),
            'positive_score': round(positive_score, 4),
            'negative_score': round(negative_score, 4),
            'neutral_score': round(neutral_score, 4),
            'emotion_scores': dict(emotion_scores),
            'emotion_percentages': emotion_percentages,
            'dominant_emotions': dominant_emotions,
            'emotion_counts': dict(emotion_counts),
            'word_sentiments': word_sentiments[:50],  # Limit for storage
            'urgency_level': urgency_level,
            'formality_level': formality_level,
            'text_statistics': text_stats,
            'insights': insights,
            'analyzed_at': datetime.utcnow().isoformat()
        }
    
    def _empty_result(self):
        """Return empty analysis result"""
        return {
            'sentiment_score': 0.0,
            'sentiment_label': 'neutral',
            'confidence': 0.0,
            'positive_score': 0.0,
            'negative_score': 0.0,
            'neutral_score': 0.0,
            'emotion_scores': {},
            'emotion_percentages': {},
            'dominant_emotions': [],
            'emotion_counts': {},
            'word_sentiments': [],
            'urgency_level': 'normal',
            'formality_level': 'neutral',
            'text_statistics': {},
            'insights': ['No content to analyze'],
            'analyzed_at': datetime.utcnow().isoformat()
        }
    
    def _analyze_text_statistics(self, text, words, sentences):
        """Analyze text characteristics"""
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'character_count': len(text),
            'avg_word_length': round(sum(len(w) for w in words) / len(words), 2) if words else 0,
            'avg_sentence_length': round(len(words) / len(sentences), 2) if sentences else 0,
            'exclamation_count': text.count('!'),
            'question_count': text.count('?'),
            'capital_ratio': round(sum(1 for c in text if c.isupper()) / len(text), 4) if text else 0,
            'has_greeting': bool(re.search(r'\b(hi|hello|hey|dear|good morning|good afternoon|good evening)\b', text.lower())),
            'has_closing': bool(re.search(r'\b(regards|sincerely|thanks|thank you|best|cheers|respectfully)\b', text.lower()))
        }
    
    def _detect_urgency(self, text, words):
        """Detect urgency level in text"""
        urgency_words = self.EMOTION_LEXICON['urgency']['words']
        urgency_count = sum(1 for w in words if w in urgency_words)
        
        # Check for caps (shouting)
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text) if text else 0
        
        # Check for multiple exclamation marks
        exclamation_intensity = text.count('!!') + text.count('!!!') * 2
        
        urgency_score = urgency_count + (caps_ratio * 10) + exclamation_intensity
        
        if urgency_score >= 5:
            return 'critical'
        elif urgency_score >= 3:
            return 'high'
        elif urgency_score >= 1:
            return 'medium'
        return 'normal'
    
    def _detect_formality(self, text, words):
        """Detect formality level"""
        formal_words = self.EMOTION_LEXICON['formal']['words']
        formal_count = sum(1 for w in words if w in formal_words)
        
        # Check for contractions (informal)
        contractions = re.findall(r"\w+'\w+", text.lower())
        
        # Check for informal greetings
        informal_greetings = re.findall(r'\b(hey|hiya|yo|sup|howdy)\b', text.lower())
        
        formality_score = formal_count - len(contractions) * 0.5 - len(informal_greetings)
        
        if formality_score >= 3:
            return 'formal'
        elif formality_score >= 1:
            return 'semi-formal'
        elif formality_score <= -2:
            return 'informal'
        return 'neutral'
    
    def _calculate_confidence(self, word_sentiments, total_words):
        """Calculate confidence score for the analysis"""
        if not word_sentiments or total_words == 0:
            return 0.0
        
        # More sentiment words = higher confidence
        sentiment_ratio = len(word_sentiments) / total_words
        
        # Consistency of sentiment (all positive/negative vs mixed)
        categories = [ws['category'] for ws in word_sentiments]
        if categories:
            positive_ratio = categories.count('positive') / len(categories)
            negative_ratio = categories.count('negative') / len(categories)
            consistency = max(positive_ratio, negative_ratio)
        else:
            consistency = 0.5
        
        confidence = (sentiment_ratio * 0.6 + consistency * 0.4)
        return min(1.0, confidence)
    
    def _generate_insights(self, sentiment_score, sentiment_label, dominant_emotions,
                          emotion_percentages, urgency_level, formality_level, text_stats):
        """Generate human-readable insights"""
        insights = []
        
        # Sentiment insight
        if sentiment_score > 0.5:
            insights.append("Strong positive sentiment detected - the communication is highly favorable")
        elif sentiment_score > 0.2:
            insights.append("Moderate positive sentiment - generally upbeat tone")
        elif sentiment_score < -0.5:
            insights.append("Strong negative sentiment detected - the communication expresses significant concern")
        elif sentiment_score < -0.2:
            insights.append("Moderate negative sentiment - some concerns or issues expressed")
        else:
            insights.append("Neutral sentiment - balanced or objective communication")
        
        # Emotion insights
        if dominant_emotions:
            emotion_insight = f"Primary emotions detected: {', '.join(dominant_emotions[:3])}"
            insights.append(emotion_insight)
        
        # Urgency insight
        if urgency_level == 'critical':
            insights.append("⚠️ CRITICAL URGENCY - Immediate attention required")
        elif urgency_level == 'high':
            insights.append("⚡ High urgency detected - Prompt response recommended")
        elif urgency_level == 'medium':
            insights.append("Medium urgency - Timely response suggested")
        
        # Formality insight
        if formality_level == 'formal':
            insights.append("Formal communication style - Professional context")
        elif formality_level == 'informal':
            insights.append("Informal communication style - Casual/friendly context")
        
        # Text statistics insights
        if text_stats.get('exclamation_count', 0) > 3:
            insights.append("High exclamation usage suggests strong emotional expression")
        
        if text_stats.get('question_count', 0) > 2:
            insights.append("Multiple questions indicate need for response/clarification")
        
        return insights


class MoodTracker:
    """
    Tracks and manages mood data over time
    Provides historical analysis and trends
    """
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.analyzer = SentimentAnalyzer()
    
    def analyze_email(self, email):
        """Analyze an email and update mood tracking"""
        from ..database.models import Email, MoodLog, SentimentAnalysis
        
        # Analyze the email content
        analysis = self.analyzer.analyze_text(f"{email.subject} {email.body}")
        
        # Store the analysis
        sentiment_record = SentimentAnalysis(
            user_id=self.user_id,
            email_id=email.id,
            sentiment_score=analysis['sentiment_score'],
            sentiment_label=analysis['sentiment_label'],
            confidence=analysis['confidence'],
            positive_score=analysis['positive_score'],
            negative_score=analysis['negative_score'],
            neutral_score=analysis['neutral_score'],
            emotion_scores=json.dumps(analysis['emotion_scores']),
            emotion_percentages=json.dumps(analysis['emotion_percentages']),
            dominant_emotions=json.dumps(analysis['dominant_emotions']),
            urgency_level=analysis['urgency_level'],
            formality_level=analysis['formality_level'],
            text_statistics=json.dumps(analysis['text_statistics']),
            insights=json.dumps(analysis['insights']),
            is_outgoing=(email.sender_id == self.user_id)
        )
        
        db.session.add(sentiment_record)
        
        # Update the email's mood fields
        email.mood_score = analysis['sentiment_score']
        email.mood_label = analysis['sentiment_label']
        
        # Update daily mood log
        self._update_daily_mood_log(analysis, email.sender_id == self.user_id)
        
        db.session.commit()
        
        return analysis
    
    def analyze_note(self, note):
        """Analyze a note's content"""
        from ..database.models import SentimentAnalysis
        
        analysis = self.analyzer.analyze_text(f"{note.title} {note.content}")
        
        sentiment_record = SentimentAnalysis(
            user_id=self.user_id,
            note_id=note.id,
            sentiment_score=analysis['sentiment_score'],
            sentiment_label=analysis['sentiment_label'],
            confidence=analysis['confidence'],
            positive_score=analysis['positive_score'],
            negative_score=analysis['negative_score'],
            neutral_score=analysis['neutral_score'],
            emotion_scores=json.dumps(analysis['emotion_scores']),
            emotion_percentages=json.dumps(analysis['emotion_percentages']),
            dominant_emotions=json.dumps(analysis['dominant_emotions']),
            urgency_level=analysis['urgency_level'],
            formality_level=analysis['formality_level'],
            text_statistics=json.dumps(analysis['text_statistics']),
            insights=json.dumps(analysis['insights']),
            is_outgoing=True
        )
        
        db.session.add(sentiment_record)
        db.session.commit()
        
        return analysis
    
    def analyze_task(self, task):
        """Analyze a task's content"""
        from ..database.models import SentimentAnalysis
        
        text = f"{task.title}"
        if task.description:
            text += f" {task.description}"
        
        analysis = self.analyzer.analyze_text(text)
        
        sentiment_record = SentimentAnalysis(
            user_id=self.user_id,
            task_id=task.id,
            sentiment_score=analysis['sentiment_score'],
            sentiment_label=analysis['sentiment_label'],
            confidence=analysis['confidence'],
            positive_score=analysis['positive_score'],
            negative_score=analysis['negative_score'],
            neutral_score=analysis['neutral_score'],
            emotion_scores=json.dumps(analysis['emotion_scores']),
            emotion_percentages=json.dumps(analysis['emotion_percentages']),
            dominant_emotions=json.dumps(analysis['dominant_emotions']),
            urgency_level=analysis['urgency_level'],
            formality_level=analysis['formality_level'],
            text_statistics=json.dumps(analysis['text_statistics']),
            insights=json.dumps(analysis['insights']),
            is_outgoing=True
        )
        
        db.session.add(sentiment_record)
        db.session.commit()
        
        return analysis
    
    def _update_daily_mood_log(self, analysis, is_outgoing):
        """Update the daily mood log with new analysis"""
        from ..database.models import MoodLog
        
        today = datetime.utcnow().date()
        
        # Get or create today's mood log
        mood_log = MoodLog.query.filter(
            MoodLog.user_id == self.user_id,
            db.func.date(MoodLog.date) == today
        ).first()
        
        if not mood_log:
            mood_log = MoodLog(
                user_id=self.user_id,
                date=datetime.utcnow(),
                positive_count=0,
                negative_count=0,
                neutral_count=0
            )
            db.session.add(mood_log)
        
        # Update counts
        if analysis['sentiment_label'] == 'positive':
            mood_log.positive_count += 1
        elif analysis['sentiment_label'] == 'negative':
            mood_log.negative_count += 1
        else:
            mood_log.neutral_count += 1
        
        # Recalculate averages
        self._recalculate_mood_averages(mood_log)
    
    def _recalculate_mood_averages(self, mood_log):
        """Recalculate average mood scores for the day"""
        from ..database.models import SentimentAnalysis
        
        today = datetime.utcnow().date()
        
        # Get all analyses for today
        analyses = SentimentAnalysis.query.filter(
            SentimentAnalysis.user_id == self.user_id,
            db.func.date(SentimentAnalysis.analyzed_at) == today
        ).all()
        
        if not analyses:
            return
        
        # Calculate averages
        incoming_scores = [a.sentiment_score for a in analyses if not a.is_outgoing]
        outgoing_scores = [a.sentiment_score for a in analyses if a.is_outgoing]
        
        if incoming_scores:
            mood_log.avg_incoming_mood = sum(incoming_scores) / len(incoming_scores)
        if outgoing_scores:
            mood_log.avg_outgoing_mood = sum(outgoing_scores) / len(outgoing_scores)
        
        # Determine trend
        self._calculate_mood_trend(mood_log)
    
    def _calculate_mood_trend(self, mood_log):
        """Calculate mood trend based on recent history"""
        from ..database.models import MoodLog
        
        # Get last 7 days of mood logs
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = MoodLog.query.filter(
            MoodLog.user_id == self.user_id,
            MoodLog.date >= week_ago
        ).order_by(MoodLog.date.asc()).all()
        
        if len(recent_logs) < 2:
            mood_log.mood_trend = 'stable'
            return
        
        # Calculate trend based on average mood
        avg_moods = []
        for log in recent_logs:
            if log.avg_incoming_mood and log.avg_outgoing_mood:
                avg_moods.append((log.avg_incoming_mood + log.avg_outgoing_mood) / 2)
            elif log.avg_incoming_mood:
                avg_moods.append(log.avg_incoming_mood)
            elif log.avg_outgoing_mood:
                avg_moods.append(log.avg_outgoing_mood)
        
        if len(avg_moods) < 2:
            mood_log.mood_trend = 'stable'
            return
        
        # Simple trend calculation
        first_half = sum(avg_moods[:len(avg_moods)//2]) / (len(avg_moods)//2)
        second_half = sum(avg_moods[len(avg_moods)//2:]) / (len(avg_moods) - len(avg_moods)//2)
        
        diff = second_half - first_half
        
        if diff > 0.1:
            mood_log.mood_trend = 'improving'
        elif diff < -0.1:
            mood_log.mood_trend = 'declining'
        else:
            mood_log.mood_trend = 'stable'
    
    def get_comprehensive_mood_report(self, days=30):
        """Generate a comprehensive mood report"""
        from ..database.models import MoodLog, SentimentAnalysis, Email
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get mood logs
        mood_logs = MoodLog.query.filter(
            MoodLog.user_id == self.user_id,
            MoodLog.date >= start_date
        ).order_by(MoodLog.date.desc()).all()
        
        # Get sentiment analyses
        analyses = SentimentAnalysis.query.filter(
            SentimentAnalysis.user_id == self.user_id,
            SentimentAnalysis.analyzed_at >= start_date
        ).order_by(SentimentAnalysis.analyzed_at.desc()).all()
        
        # Calculate comprehensive statistics
        total_positive = sum(log.positive_count for log in mood_logs)
        total_negative = sum(log.negative_count for log in mood_logs)
        total_neutral = sum(log.neutral_count for log in mood_logs)
        
        # Emotion distribution
        emotion_totals = defaultdict(float)
        for analysis in analyses:
            if analysis.emotion_scores:
                scores = json.loads(analysis.emotion_scores)
                for emotion, score in scores.items():
                    emotion_totals[emotion] += score
        
        # Urgency distribution
        urgency_distribution = {'critical': 0, 'high': 0, 'medium': 0, 'normal': 0}
        for analysis in analyses:
            urgency_distribution[analysis.urgency_level] += 1
        
        # Formality distribution
        formality_distribution = {'formal': 0, 'semi-formal': 0, 'neutral': 0, 'informal': 0}
        for analysis in analyses:
            formality_distribution[analysis.formality_level] += 1
        
        # Calculate overall sentiment
        all_scores = [a.sentiment_score for a in analyses]
        avg_sentiment = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Get most common emotions
        sorted_emotions = sorted(emotion_totals.items(), key=lambda x: x[1], reverse=True)
        top_emotions = sorted_emotions[:5]
        
        # Generate insights
        insights = self._generate_report_insights(
            avg_sentiment, total_positive, total_negative, total_neutral,
            top_emotions, urgency_distribution, mood_logs
        )
        
        return {
            'period_days': days,
            'total_analyzed': len(analyses),
            'overall_sentiment': round(avg_sentiment, 4),
            'sentiment_label': 'positive' if avg_sentiment > 0.1 else ('negative' if avg_sentiment < -0.1 else 'neutral'),
            'sentiment_distribution': {
                'positive': total_positive,
                'negative': total_negative,
                'neutral': total_neutral
            },
            'emotion_distribution': dict(sorted_emotions),
            'top_emotions': top_emotions,
            'urgency_distribution': urgency_distribution,
            'formality_distribution': formality_distribution,
            'mood_logs': mood_logs,
            'recent_analyses': analyses[:20],
            'insights': insights,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _generate_report_insights(self, avg_sentiment, positive, negative, neutral,
                                  top_emotions, urgency_dist, mood_logs):
        """Generate insights for the mood report"""
        insights = []
        
        # Overall sentiment insight
        if avg_sentiment > 0.3:
            insights.append("🌟 Your communications have been predominantly positive!")
        elif avg_sentiment < -0.3:
            insights.append("💭 Your recent communications show some concerns. Consider reaching out for support if needed.")
        else:
            insights.append("📊 Your communication sentiment has been balanced.")
        
        # Sentiment ratio insight
        total = positive + negative + neutral
        if total > 0:
            positive_ratio = positive / total
            if positive_ratio > 0.6:
                insights.append("✨ Great job maintaining positive interactions!")
            elif positive_ratio < 0.3:
                insights.append("💡 Consider focusing on more positive communication patterns.")
        
        # Emotion insights
        if top_emotions:
            top_emotion = top_emotions[0][0]
            insights.append(f"🎭 Most expressed emotion: {top_emotion}")
        
        # Urgency insights
        if urgency_dist.get('critical', 0) > 0:
            insights.append(f"⚠️ {urgency_dist['critical']} critical urgency communications detected")
        
        # Trend insight
        if len(mood_logs) >= 3:
            recent_trend = mood_logs[0].mood_trend if mood_logs[0].mood_trend else 'stable'
            if recent_trend == 'improving':
                insights.append("📈 Your mood trend is improving! Keep it up!")
            elif recent_trend == 'declining':
                insights.append("📉 Your mood trend has been declining. Take care of yourself.")
        
        return insights


# Global analyzer instance
_analyzer = None

def get_sentiment_analyzer():
    """Get or create the global sentiment analyzer"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


def analyze_content(text):
    """Quick function to analyze text content"""
    analyzer = get_sentiment_analyzer()
    return analyzer.analyze_text(text)


def track_user_mood(user_id):
    """Get a mood tracker for a user"""
    return MoodTracker(user_id)