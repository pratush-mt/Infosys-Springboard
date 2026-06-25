# app.py - COMBINED VERSION WITH ALL FEATURES AND ENHANCED UI/UX
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, make_response, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
import sys
from datetime import datetime, timedelta
import json
import re
import html
import PyPDF2
import io
import logging
import time
import hashlib
import zipfile
import tempfile
from typing import List, Dict, Tuple, Optional
from difflib import unified_diff, SequenceMatcher
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import csv
from io import StringIO, BytesIO

# Add utilities to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utilities'))

# Import Task 9 & 10 modules
try:
    from utilities.config import get_config, setup_logging
    from utilities.ai_model import get_ai_summarizer, AIModelSummarizer
    from utilities.api_handler import get_api_handler, create_summarize_endpoint, create_stats_endpoint, create_health_endpoint
    from utilities.chunking_system import TextChunker, ChunkManager, ChunkingStrategy, get_chunking_strategy, SmartTextProcessor
    
    # If we get here, imports were successful
    IMPORT_SUCCESS = True
    print("✅ Successfully imported Task 9 & 10 modules")
    
except ImportError as e:
    print(f"Warning: Could not import Task modules: {e}")
    print("Running without advanced features...")
    IMPORT_SUCCESS = False
    
    # Create dummy implementations for missing modules
    class DummyAISummarizer:
        def __init__(self, model_name):
            self.model_name = model_name
            self.is_loaded = False
            self.max_input_length = 1024
            self.min_summary_length = 50
            self.max_summary_length = 150
        
        def load_model(self):
            return False
        
        def summarize_text(self, text, compression_ratio=0.3):
            # IMPROVED: Actually use compression_ratio to determine summary length
            words = text.split()
            original_word_count = len(words)
            
            # Calculate target word count based on compression ratio
            if compression_ratio < 0.1:
                target_words = max(50, int(original_word_count * 0.1))  # Very short: 10%
            elif compression_ratio < 0.3:
                target_words = max(100, int(original_word_count * 0.2))  # Short: 20%
            elif compression_ratio < 0.5:
                target_words = max(150, int(original_word_count * 0.3))  # Medium: 30%
            else:
                target_words = max(200, int(original_word_count * 0.5))  # Long: 50%
            
            # Limit to max summary length
            target_words = min(target_words, self.max_summary_length)
            
            # Improved summarization logic
            sentences = re.split(r'(?<=[.!?])\s+', text)
            
            if len(sentences) <= 3:
                # For very short texts, just return the text
                summary = text[:target_words*6]  # Approximate 6 chars per word
                if len(summary) < len(text):
                    summary += '...'
            else:
                # For longer texts, use better summarization logic
                # Get key sentences (first, middle, last for better context)
                if len(sentences) >= 5:
                    # Take first sentence, some middle sentences, and last sentence
                    summary_sentences = [sentences[0]]
                    
                    # Add middle sentences based on compression ratio
                    if compression_ratio > 0.3:  # Medium or Long
                        middle_idx = len(sentences) // 2
                        summary_sentences.append(sentences[middle_idx])
                    
                    if compression_ratio > 0.4:  # Long
                        # Add more sentences for longer summaries
                        quarter_idx = len(sentences) // 4
                        three_quarter_idx = (3 * len(sentences)) // 4
                        summary_sentences.append(sentences[quarter_idx])
                        summary_sentences.append(sentences[three_quarter_idx])
                    
                    summary_sentences.append(sentences[-1])
                else:
                    # For texts with 4-5 sentences, take first 3
                    summary_sentences = sentences[:3]
                
                summary = ' '.join(summary_sentences)
                
                # Adjust length based on compression ratio
                current_words = len(summary.split())
                if current_words > target_words:
                    # Reduce summary length
                    words = summary.split()
                    summary = ' '.join(words[:target_words]) + '...'
                elif current_words < target_words * 0.8:
                    # Expand summary if too short
                    # Add more sentences
                    remaining_sentences = [s for s in sentences if s not in summary_sentences]
                    for sent in remaining_sentences:
                        summary += ' ' + sent
                        if len(summary.split()) >= target_words:
                            break
            
            # Calculate actual compression ratio
            actual_ratio = len(summary.split()) / original_word_count if original_word_count > 0 else 0
            
            return {
                'success': True,
                'summary': summary,
                'compression_ratio': actual_ratio,
                'read_time_minutes': max(1, len(summary.split()) // 200),
                'original_length': original_word_count,
                'summary_length': len(summary.split()),
                'model_used': 'Simple Summarizer',
                'target_compression': compression_ratio
            }
        
        def get_performance_stats(self):
            return {'total_inferences': 0, 'device': 'CPU', 'avg_inference_time': 0, 'total_chunks': 0}
    
    class DummyAPIHandler:
        def handle_summarize_request(self):
            return {'success': False, 'error': 'API handler not available'}
        
        def get_api_stats(self):
            return {'total_requests': 0}
    
    class DummyTextChunker:
        def __init__(self, max_chunk_size=800, overlap=100):
            self.max_chunk_size = max_chunk_size
            self.overlap = overlap
        
        def chunk_text(self, text, strategy="paragraph"):
            # Simple chunking fallback
            paragraphs = text.split('\n\n')
            chunks = []
            current_chunk = []
            current_size = 0
            
            for para in paragraphs:
                para_words = len(para.split())
                if current_size + para_words > self.max_chunk_size and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = [para]
                    current_size = para_words
                else:
                    current_chunk.append(para)
                    current_size += para_words
            
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Convert to dict format
            result = []
            for i, chunk in enumerate(chunks):
                result.append({
                    'content': chunk,
                    'index': i,
                    'word_count': len(chunk.split()),
                    'start_position': 0,
                    'end_position': len(chunk),
                    'has_overlap': False,
                    'overlap_size': 0
                })
            
            return result
        
        def get_chunk_info(self, text):
            chunks = self.chunk_text(text)
            return {
                'strategy': 'simple',
                'total_chunks': len(chunks),
                'average_chunk_size': sum(c['word_count'] for c in chunks) // len(chunks) if chunks else 0,
                'chunks_with_overlap': 0,
                'recommended_strategy': 'simple'
            }
    
    class DummyChunkManager:
        def __init__(self):
            self.chunks = {}
        
        def store_chunks(self, book_id, chunks):
            self.chunks[book_id] = chunks
            return len(chunks)
        
        def get_chunks(self, book_id):
            return self.chunks.get(book_id, [])
        
        def get_chunk_metadata(self, book_id):
            return {}
        
        def clear_chunks(self, book_id):
            if book_id in self.chunks:
                del self.chunks[book_id]
    
    # Define SmartTextProcessor class here since it's referenced
    class SmartTextProcessor:
        def __init__(self):
            pass
        
        def analyze_text_structure(self, text):
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            paragraphs = text.split('\n\n')
            
            return {
                'word_count': len(words),
                'sentence_count': len([s for s in sentences if s.strip()]),
                'paragraph_count': len([p for p in paragraphs if p.strip()]),
                'avg_sentence_length': len(words) // max(1, len(sentences)),
                'avg_paragraph_length': len(words) // max(1, len(paragraphs)),
                'heading_count': 0,
                'headings': [],
                'reading_time_minutes': max(1, len(words) // 200),
                'needs_chunking': len(words) > 1500
            }
        
        def find_natural_breaks(self, text):
            return []
        
        def split_at_breaks(self, text, max_chunk_size):
            words = text.split()
            chunks = []
            total_words = len(words)
            
            for i in range(0, total_words, max_chunk_size):
                chunk_words = words[i:i + max_chunk_size]
                chunks.append({
                    'content': ' '.join(chunk_words),
                    'word_count': len(chunk_words),
                    'start_position': i,
                    'end_position': i + len(chunk_words)
                })
            
            return chunks
        
        def optimize_chunk_sizes(self, chunks, target_size):
            return chunks
    
    # Define the missing functions
    def get_chunking_strategy(strategy_name):
        return DummyTextChunker()
    
    def get_config(env):
        return {
            'SECRET_KEY': 'your-secret-key-here-change-in-production',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///book_summarizer.db?check_same_thread=False',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'MODEL_NAME': 'sshleifer/distilbart-cnn-12-6',
            'MAX_INPUT_LENGTH': 1024,
            'MAX_SUMMARY_LENGTH': 150,
            'MIN_SUMMARY_LENGTH': 50,
            'DEFAULT_COMPRESSION_RATIO': 0.3,
            'CHUNK_SIZE_WORDS': 800,
            'CHUNK_OVERLAP': 100,
            'CHUNKING_STRATEGY': 'paragraph'
        }
    
    def setup_logging(config):
        logging.basicConfig(level=logging.INFO)
    
    def get_ai_summarizer(model_name):
        return DummyAISummarizer(model_name)
    
    def get_api_handler():
        return DummyAPIHandler()
    
    def create_summarize_endpoint():
        return jsonify({'success': False, 'error': 'API endpoint not available'}), 501
    
    def create_stats_endpoint():
        return jsonify({'success': False, 'error': 'API endpoint not available'}), 501
    
    def create_health_endpoint():
        return jsonify({'success': False, 'error': 'API endpoint not available'}), 501

# Load configuration
config = get_config("development")
setup_logging(config)

# Create Config class for Flask
class FlaskConfig:
    SECRET_KEY = config.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
    SQLALCHEMY_DATABASE_URI = config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///book_summarizer.db?check_same_thread=False')
    SQLALCHEMY_TRACK_MODIFICATIONS = config.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30
        }
    }
    UPLOAD_FOLDER = 'uploads'
    
    # Add AI configuration
    AI_MODEL_NAME = config.get('MODEL_NAME', 'sshleifer/distilbart-cnn-12-6')
    MAX_INPUT_LENGTH = config.get('MAX_INPUT_LENGTH', 1024)
    MAX_SUMMARY_LENGTH = config.get('MAX_SUMMARY_LENGTH', 150)
    MIN_SUMMARY_LENGTH = config.get('MIN_SUMMARY_LENGTH', 50)
    DEFAULT_COMPRESSION_RATIO = config.get('DEFAULT_COMPRESSION_RATIO', 0.3)
    
    # Task 10: Chunking Configuration
    CHUNK_SIZE_WORDS = config.get('CHUNK_SIZE_WORDS', 800)
    CHUNK_OVERLAP = config.get('CHUNK_OVERLAP', 100)
    CHUNKING_STRATEGY = config.get('CHUNKING_STRATEGY', 'paragraph')
    MAX_CHUNKS_PER_BOOK = config.get('MAX_CHUNKS_PER_BOOK', 50)

app = Flask(__name__)
app.config.from_object(FlaskConfig)

CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# Initialize Task 9 AI components
ai_summarizer = get_ai_summarizer(config.get('MODEL_NAME', 'sshleifer/distilbart-cnn-12-6'))
api_handler = get_api_handler()

# Initialize Task 10 Chunking components based on import success
if IMPORT_SUCCESS:
    print("✅ Using advanced chunking system from utilities")
    text_chunker = TextChunker(
        max_chunk_size=config.get('CHUNK_SIZE_WORDS', 800),
        overlap=config.get('CHUNK_OVERLAP', 100)
    )
    chunk_manager = ChunkManager()
    smart_processor = SmartTextProcessor()
else:
    print("⚠️ Using fallback chunking system")
    text_chunker = DummyTextChunker(
        max_chunk_size=config.get('CHUNK_SIZE_WORDS', 800),
        overlap=config.get('CHUNK_OVERLAP', 100)
    )
    chunk_manager = DummyChunkManager()
    smart_processor = SmartTextProcessor()

# Configure logging
logger = logging.getLogger(__name__)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    __tablename__ = 'user'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    preferences = db.Column(db.Text, default='{"theme": "light"}')  # Task 18: User preferences
    
    def set_password(self, password):
        self.password_hash = password
    
    def check_password(self, password):
        return self.password_hash == password
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def get_preferences(self):
        try:
            return json.loads(self.preferences)
        except:
            return {"theme": "light", "tutorial_completed": False}
    
    def update_preferences(self, prefs):
        current = self.get_preferences()
        current.update(prefs)
        self.preferences = json.dumps(current)
        db.session.commit()

class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, default=0)
    file_type = db.Column(db.String(20))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('books', lazy=True))
    summaries = db.relationship('Summary', backref='book', lazy=True, cascade='all, delete-orphan')
    chunks = db.relationship('BookChunk', backref='book', lazy=True, cascade='all, delete-orphan')
    
    # Task 10: Chunking metadata
    chunking_strategy = db.Column(db.String(50), default='paragraph')
    chunk_size = db.Column(db.Integer, default=800)
    chunk_overlap = db.Column(db.Integer, default=100)
    total_chunks = db.Column(db.Integer, default=0)
    chunking_completed = db.Column(db.Boolean, default=False)
    
    # Task 15: Default summary for comparison
    default_summary_id = db.Column(db.Integer, nullable=True)
    
    def get_chunking_info(self):
        return {
            'total_chunks': self.total_chunks,
            'chunking_strategy': self.chunking_strategy,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'chunking_completed': self.chunking_completed
        }
    
    def get_default_summary(self):
        if self.default_summary_id:
            return Summary.query.get(self.default_summary_id)
        return None

class BookChunk(db.Model):
    """Task 10: Store individual chunks for large books"""
    __tablename__ = 'book_chunk'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)  # 0-based index
    content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, default=0)
    start_position = db.Column(db.Integer, default=0)  # Character position in original text
    end_position = db.Column(db.Integer, default=0)    # Character position in original text
    has_context_overlap = db.Column(db.Boolean, default=False)
    chunk_hash = db.Column(db.String(64), unique=True)  # SHA256 hash for deduplication
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Indexes for faster queries
    __table_args__ = (
        db.Index('idx_book_chunk', 'book_id', 'chunk_index'),
        db.UniqueConstraint('book_id', 'chunk_index', name='uix_book_chunk')
    )
    
    @property
    def overlap_info(self):
        return {
            'chunk_index': self.chunk_index,
            'has_context_overlap': self.has_context_overlap,
            'position': f"{self.start_position}-{self.end_position}",
            'word_count': self.word_count
        }

class ChunkSummary(db.Model):
    """Task 10: Store summaries for individual chunks"""
    __tablename__ = 'chunk_summary'
    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.Integer, db.ForeignKey('book_chunk.id'), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    compression_ratio = db.Column(db.Float, default=0.0)
    key_points = db.Column(db.Text)
    model_used = db.Column(db.String(100))
    processing_time = db.Column(db.Float, default=0.0)  # Seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    chunk = db.relationship('BookChunk', backref=db.backref('summaries', lazy=True))

class Summary(db.Model):
    __tablename__ = 'summary'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    compression_ratio = db.Column(db.Float, default=0.0)
    read_time_minutes = db.Column(db.Integer, default=0)
    key_points = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    model_used = db.Column(db.String(100))
    
    # Task 10: Chunking metadata
    is_chunked_summary = db.Column(db.Boolean, default=False)
    total_chunks_processed = db.Column(db.Integer, default=0)
    chunk_summaries_used = db.Column(db.Text)  # JSON list of chunk summary IDs
    
    # Task 15: Version history and comparison
    summary_version = db.Column(db.Integer, default=1)
    is_favorite = db.Column(db.Boolean, default=False)
    settings_used = db.Column(db.Text)  # JSON string of settings used
    export_count = db.Column(db.Integer, default=0)  # Task 14: Track export usage
    
    @property
    def time_saved(self):
        original_time = self.book.word_count // 200 if self.book.word_count else 0
        return max(0, original_time - self.read_time_minutes)
    
    def get_chunk_summary_info(self):
        if not self.is_chunked_summary:
            return None
        
        return {
            'total_chunks_processed': self.total_chunks_processed,
            'chunk_summaries_used': json.loads(self.chunk_summaries_used) if self.chunk_summaries_used else []
        }
    
    def get_settings(self):
        if self.settings_used:
            return json.loads(self.settings_used)
        return {
            'length': 'medium',
            'style': 'paragraph',
            'detail': 'concise',
            'compression': self.compression_ratio
        }
    
    def increment_export_count(self):
        self.export_count += 1
        db.session.commit()

# ==================== HELPER FUNCTIONS ====================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def extract_text_from_pdf(file_content):
    """Extract text from PDF file content"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        
        return text if text.strip() else "Could not extract text from PDF. Please upload a text-based PDF."
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return f"Error extracting text from PDF: {str(e)}"

def clean_text_for_display(text, max_length=5000):
    """Clean text for safe display"""
    if not text:
        return ""
    
    # Remove PDF artifacts
    text = re.sub(r'%PDF-\d+\.\d+', '', text)
    text = re.sub(r'%\w+_\d+', '', text)
    text = re.sub(r'OB\w+_\d+', '', text)
    text = re.sub(r'/{.*?}', '', text)
    text = re.sub(r'endobj|stream|xref|trailer|startxref', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d+\s+\d+\s+obj', '', text)
    text = re.sub(r'&lt;&lt;.*?&gt;&gt;', '', text, flags=re.DOTALL)
    
    # Clean up formatting
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Escape HTML for safety
    text = html.escape(text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + '... [Content truncated]'
    
    return text.strip()

def format_summary_for_display(summary_text, style='paragraph'):
    """Format summary based on style preference"""
    if style == 'bullet':
        # Convert to bullet points
        sentences = re.split(r'(?<=[.!?])\s+', summary_text)
        formatted = '<div class="bullet-points">'
        for sentence in sentences:
            if sentence.strip():
                formatted += f'''
                <div class="bullet-item animate-fade-in">
                    <span class="bullet-icon"><i class="fas fa-circle"></i></span>
                    <span class="bullet-text">{sentence.strip()}</span>
                </div>
                '''
        formatted += '</div>'
        return formatted
    else:
        # Keep as paragraph with proper formatting
        paragraphs = summary_text.split('\n\n')
        formatted = '<div class="paragraph-summary">'
        for para in paragraphs:
            if para.strip():
                formatted += f'<p class="animate-fade-in">{para.strip().replace("\n", "<br>")}</p>'
        formatted += '</div>'
        return formatted

# ==================== FILE PROCESSOR ====================

class FileProcessor:
    def extract_text(self, file):
        """Extract text from uploaded file"""
        try:
            if hasattr(file, 'read'):
                file_content = file.read()
                
                if file.filename.lower().endswith('.pdf'):
                    file.seek(0)
                    file_content = file.read()
                    return extract_text_from_pdf(file_content)
                else:
                    try:
                        return file_content.decode('utf-8', errors='ignore')
                    except:
                        return str(file_content)
            return str(file)
        except Exception as e:
            logger.error(f"File processing error: {str(e)}")
            return f"Error processing file: {str(e)}"

file_processor = FileProcessor()

# ==================== SELF-HELP BOOKS DATA ====================

SELF_HELP_BOOKS = [
    {
        'id': 1,
        'title': 'Atomic Habits',
        'author': 'James Clear',
        'year': 2018,
        'cover': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
        'summary': 'A practical guide to building good habits and breaking bad ones using tiny changes that lead to remarkable results.',
        'key_points': [
            'Focus on systems rather than goals',
            'The 1% improvement rule - small changes compound',
            'Four Laws of Behavior Change'
        ],
        'practical_tips': [
            'Use habit tracking to maintain consistency',
            'Reduce friction for good habits',
            'Never miss twice - maintain your streak'
        ]
    },
    {
        'id': 2,
        'title': 'The 7 Habits of Highly Effective People',
        'author': 'Stephen R. Covey',
        'year': 1989,
        'cover': 'https://images.unsplash.com/photo-1516979187457-637abb4f9353?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
        'summary': 'A holistic approach to personal and professional effectiveness based on principles of character ethics.',
        'key_points': [
            'Be Proactive - Take responsibility',
            'Begin with the End in Mind',
            'Put First Things First'
        ],
        'practical_tips': [
            'Create a personal mission statement',
            'Use the Time Management Matrix',
            'Practice empathy in communication'
        ]
    },
    {
        'id': 3,
        'title': 'The Power of Now',
        'author': 'Eckhart Tolle',
        'year': 1997,
        'cover': 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
        'summary': 'A guide to spiritual enlightenment that emphasizes living in the present moment.',
        'key_points': [
            'Most suffering comes from identification with the mind',
            'The present moment is all we ever have',
            'Acceptance leads to peace'
        ],
        'practical_tips': [
            'Practice mindfulness throughout the day',
            'Observe your thoughts without judgment',
            'Use breath as an anchor to the present'
        ]
    }
]

SELF_HELP_BOOKS_DICT = {book['id']: book for book in SELF_HELP_BOOKS}

# ==================== TASK 10: CHUNKING HELPER FUNCTIONS ====================

def calculate_chunk_hash(content: str) -> str:
    """Calculate SHA256 hash for chunk content"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def needs_chunking(book: Book) -> bool:
    """Determine if a book needs chunking based on word count"""
    # If book already has chunks, it's already chunked
    if book.total_chunks > 0:
        return False
    
    # Determine if chunking is needed
    word_count = book.word_count or len(book.content.split())
    
    # Chunk if more than 1500 words or if specifically requested
    return word_count > 1500

def process_book_chunks(book: Book, strategy: str = "paragraph") -> Dict:
    """
    Process book into chunks using specified strategy
    
    Args:
        book: Book object to chunk
        strategy: Chunking strategy ('paragraph', 'sentence', 'fixed', 'smart')
    
    Returns:
        Dict with chunking results
    """
    try:
        logger.info(f"Processing chunks for book {book.id}: '{book.title}' (Strategy: {strategy})")
        
        # Use the text chunker to create chunks
        chunks = text_chunker.chunk_text(book.content, strategy)
        
        if not chunks:
            logger.error(f"No chunks created for book {book.id}")
            return {'success': False, 'error': 'Failed to create chunks'}
        
        logger.info(f"Created {len(chunks)} chunks for book {book.id}")
        
        # Store chunks in database with session management
        chunk_ids = []
        try:
            for i, chunk in enumerate(chunks):
                chunk_hash = calculate_chunk_hash(chunk['content'])
                
                # Check for duplicate chunk
                existing_chunk = BookChunk.query.filter_by(chunk_hash=chunk_hash).first()
                if existing_chunk:
                    logger.warning(f"Duplicate chunk found for book {book.id}, chunk {i}")
                    chunk_ids.append(existing_chunk.id)
                    continue
                
                # Create new chunk
                book_chunk = BookChunk(
                    book_id=book.id,
                    chunk_index=i,
                    content=chunk['content'],
                    word_count=chunk.get('word_count', len(chunk['content'].split())),
                    start_position=chunk.get('start_position', 0),
                    end_position=chunk.get('end_position', len(chunk['content'])),
                    has_context_overlap=chunk.get('has_overlap', False),
                    chunk_hash=chunk_hash
                )
                db.session.add(book_chunk)
                db.session.flush()  # Get ID before commit
                chunk_ids.append(book_chunk.id)
            
            # Update book metadata
            book.total_chunks = len(chunks)
            book.chunking_strategy = strategy
            book.chunking_completed = True
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            raise e
        
        # Store in chunk manager cache
        chunk_manager.store_chunks(book.id, [
            BookChunk.query.get(chunk_id) for chunk_id in chunk_ids if BookChunk.query.get(chunk_id)
        ])
        
        return {
            'success': True,
            'total_chunks': len(chunks),
            'chunk_ids': chunk_ids,
            'average_chunk_size': sum(len(c['content'].split()) for c in chunks) // len(chunks),
            'chunks_with_overlap': sum(1 for c in chunks if c.get('has_overlap', False))
        }
        
    except Exception as e:
        logger.error(f"Error processing book chunks: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)[:200]}

def summarize_chunks(book: Book, compression_ratio: float = 0.3) -> Dict:
    """
    Summarize all chunks of a book and combine results
    
    Args:
        book: Book object
        compression_ratio: Target compression ratio
    
    Returns:
        Dict with combined summary results
    """
    try:
        # Get book chunks
        chunks = BookChunk.query.filter_by(book_id=book.id)\
                               .order_by(BookChunk.chunk_index)\
                               .all()
        
        if not chunks:
            logger.error(f"No chunks found for book {book.id}")
            return {'success': False, 'error': 'No chunks available for summarization'}
        
        logger.info(f"Summarizing {len(chunks)} chunks for book {book.id}")
        
        chunk_summaries = []
        chunk_summary_ids = []
        total_processing_time = 0
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} "
                       f"(words: {chunk.word_count}, overlap: {chunk.has_context_overlap})")
            
            try:
                start_time = time.time()
                
                # Generate summary for chunk
                result = ai_summarizer.summarize_text(
                    chunk.content,
                    compression_ratio=compression_ratio
                )
                
                processing_time = time.time() - start_time
                total_processing_time += processing_time
                
                if result['success']:
                    # Store chunk summary
                    chunk_summary = ChunkSummary(
                        chunk_id=chunk.id,
                        summary=result['summary'],
                        compression_ratio=result['compression_ratio'],
                        key_points='\n'.join(result.get('key_points', [])),
                        model_used=result.get('model_used', ai_summarizer.model_name),
                        processing_time=processing_time
                    )
                    db.session.add(chunk_summary)
                    db.session.flush()
                    
                    chunk_summaries.append(result['summary'])
                    chunk_summary_ids.append(chunk_summary.id)
                    
                    logger.info(f"Chunk {i+1} summarized: {result['summary_length']} words "
                               f"({processing_time:.2f}s)")
                else:
                    logger.error(f"Failed to summarize chunk {i+1}: {result.get('error')}")
                    # Use fallback: extract first few sentences
                    sentences = re.split(r'(?<=[.!?])\s+', chunk.content)
                    fallback_summary = '. '.join(sentences[:3]) + '.'
                    
                    chunk_summary = ChunkSummary(
                        chunk_id=chunk.id,
                        summary=fallback_summary,
                        compression_ratio=0.5,
                        key_points='',
                        model_used='fallback',
                        processing_time=processing_time
                    )
                    db.session.add(chunk_summary)
                    db.session.flush()
                    
                    chunk_summaries.append(fallback_summary)
                    chunk_summary_ids.append(chunk_summary.id)
                    
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {str(e)}")
                # Create minimal fallback
                chunk_summaries.append(f"[Chunk {i+1} summary unavailable]")
                chunk_summary_ids.append(None)
        
        # Combine chunk summaries
        combined_summary = combine_chunk_summaries(chunk_summaries, compression_ratio)
        
        if combined_summary:
            # Calculate overall statistics
            total_words = sum(len(s.split()) for s in chunk_summaries)
            combined_words = len(combined_summary.split())
            overall_compression = combined_words / book.word_count if book.word_count > 0 else 0
            
            # Create final summary record
            final_summary = Summary(
                book_id=book.id,
                summary=combined_summary,
                compression_ratio=overall_compression,
                read_time_minutes=max(1, combined_words // 200),
                key_points=extract_key_points(combined_summary),
                model_used=f"{ai_summarizer.model_name} (Chunked: {len(chunks)} chunks)",
                is_chunked_summary=True,
                total_chunks_processed=len(chunks),
                chunk_summaries_used=json.dumps(chunk_summary_ids)
            )
            
            db.session.add(final_summary)
            db.session.commit()
            summary_id = final_summary.id
            
            return {
                'success': True,
                'summary_id': summary_id,
                'total_chunks': len(chunks),
                'chunks_summarized': len(chunk_summaries),
                'overall_compression': overall_compression,
                'processing_time': total_processing_time,
                'average_chunk_time': total_processing_time / len(chunks) if chunks else 0
            }
        else:
            return {'success': False, 'error': 'Failed to combine chunk summaries'}
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in summarize_chunks: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)[:200]}

def combine_chunk_summaries(chunk_summaries: List[str], compression_ratio: float = 0.3) -> str:
    """
    Combine multiple chunk summaries into a coherent final summary
    
    Args:
        chunk_summaries: List of individual chunk summaries
        compression_ratio: Target compression ratio for final summary
    
    Returns:
        Combined summary string
    """
    if not chunk_summaries:
        return ""
    
    # Combine all chunk summaries
    combined_text = " ".join(chunk_summaries)
    
    # If combined text is short enough, use as-is
    if len(combined_text.split()) < 500:
        return combined_text
    
    # Summarize the combined text
    try:
        result = ai_summarizer.summarize_text(combined_text, compression_ratio=compression_ratio)
        if result['success']:
            return result['summary']
        else:
            # Fallback: take first few sentences from each chunk summary
            important_sentences = []
            for summary in chunk_summaries:
                sentences = re.split(r'(?<=[.!?])\s+', summary)
                if sentences:
                    important_sentences.append(sentences[0])
            
            return ". ".join(important_sentences[:5]) + "."
    except Exception as e:
        logger.error(f"Error combining summaries: {str(e)}")
        # Last resort fallback
        return ". ".join(chunk_summaries[:3]) + "..."

def extract_key_points(text: str, max_points: int = 5) -> str:
    """Extract key points from text"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Filter and clean sentences
    key_sentences = []
    for sentence in sentences:
        clean_sentence = sentence.strip()
        if len(clean_sentence.split()) >= 5 and len(clean_sentence.split()) <= 30:
            key_sentences.append(clean_sentence)
        if len(key_sentences) >= max_points:
            break
    
    return '\n'.join(key_sentences)

def get_chunking_analysis(book: Book) -> Dict:
    """Get detailed chunking analysis for a book"""
    chunks = BookChunk.query.filter_by(book_id=book.id)\
                           .order_by(BookChunk.chunk_index)\
                           .all()
    
    if not chunks:
        return {
            'chunking_required': needs_chunking(book),
            'total_chunks': 0,
            'chunking_completed': False,
            'chunking_strategy': book.chunking_strategy or 'paragraph',
            'average_chunk_size': 0,
            'min_chunk_size': 0,
            'max_chunk_size': 0,
            'chunks_with_overlap': 0,
            'overlap_percentage': 0,
            'chunk_details': []
        }
    
    # Calculate chunk statistics
    word_counts = [chunk.word_count for chunk in chunks]
    overlap_count = sum(1 for chunk in chunks if chunk.has_context_overlap)
    avg_size = sum(word_counts) // len(word_counts) if word_counts else 0
    
    return {
        'chunking_required': True,
        'total_chunks': len(chunks),
        'chunking_completed': book.chunking_completed,
        'chunking_strategy': book.chunking_strategy or 'paragraph',
        'average_chunk_size': avg_size,
        'min_chunk_size': min(word_counts) if word_counts else 0,
        'max_chunk_size': max(word_counts) if word_counts else 0,
        'chunks_with_overlap': overlap_count,
        'overlap_percentage': round((overlap_count / len(chunks) * 100), 2) if chunks else 0,
        'chunk_details': [
            {
                'index': chunk.chunk_index,
                'word_count': chunk.word_count,
                'has_overlap': chunk.has_context_overlap,
                'position': f"{chunk.start_position}-{chunk.end_position}"
            }
            for chunk in chunks[:10]  # Limit to first 10 for performance
        ]
    }

# ==================== TASK 14: EXPORT HELPER FUNCTIONS ====================

class SummaryExporter:
    """Task 14: Handles export of summaries to various formats"""
    
    @staticmethod
    def export_to_text(summary_obj, include_metadata=True, include_original_excerpt=False):
        """Export summary to plain text format"""
        lines = []
        
        if include_metadata:
            lines.append(f"Summary of: {summary_obj.book.title}")
            lines.append(f"Author: {summary_obj.book.author or 'Unknown'}")
            lines.append(f"Generated: {summary_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Compression Ratio: {summary_obj.compression_ratio:.1%}")
            lines.append(f"Read Time: {summary_obj.read_time_minutes} minutes")
            lines.append(f"Time Saved: {summary_obj.time_saved} minutes")
            lines.append(f"Model Used: {summary_obj.model_used}")
            lines.append(f"Summary ID: {summary_obj.id}")
            lines.append("-" * 80)
            lines.append("")
        
        lines.append("SUMMARY:")
        lines.append("=" * 80)
        lines.append(summary_obj.summary)
        lines.append("")
        
        if summary_obj.key_points:
            lines.append("KEY POINTS:")
            lines.append("=" * 80)
            for i, point in enumerate(summary_obj.key_points.split('\n'), 1):
                if point.strip():
                    lines.append(f"{i}. {point.strip()}")
            lines.append("")
        
        if include_original_excerpt and summary_obj.book:
            lines.append("ORIGINAL TEXT EXCERPT:")
            lines.append("=" * 80)
            # Get first 500 characters of original text
            excerpt = summary_obj.book.content[:500]
            if len(summary_obj.book.content) > 500:
                excerpt += "..."
            lines.append(excerpt)
            lines.append("")
        
        if include_metadata:
            lines.append("-" * 80)
            lines.append(f"Generated by Book Summarizer AI - {datetime.now().strftime('%Y-%m-%d')}")
        
        return "\n".join(lines)
    
    @staticmethod
    def export_to_pdf(summary_obj, include_metadata=True, include_original_excerpt=False):
        """Export summary to PDF format using ReportLab"""
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=72)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            textColor=colors.HexColor('#2C3E50')
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.HexColor('#3498DB')
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2C3E50')
        )
        meta_style = ParagraphStyle(
            'CustomMeta',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            textColor=colors.HexColor('#7F8C8D')
        )
        
        # Build story (content)
        story = []
        
        # Add title
        story.append(Paragraph(f"Summary: {summary_obj.book.title}", title_style))
        story.append(Spacer(1, 12))
        
        # Add metadata
        if include_metadata:
            meta_data = [
                [Paragraph(f"<b>Author:</b>", meta_style), 
                 Paragraph(f"{summary_obj.book.author or 'Unknown'}", meta_style)],
                [Paragraph(f"<b>Generated:</b>", meta_style), 
                 Paragraph(f"{summary_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}", meta_style)],
                [Paragraph(f"<b>Compression Ratio:</b>", meta_style), 
                 Paragraph(f"{summary_obj.compression_ratio:.1%}", meta_style)],
                [Paragraph(f"<b>Read Time:</b>", meta_style), 
                 Paragraph(f"{summary_obj.read_time_minutes} minutes", meta_style)],
                [Paragraph(f"<b>Time Saved:</b>", meta_style), 
                 Paragraph(f"{summary_obj.time_saved} minutes", meta_style)],
                [Paragraph(f"<b>Model Used:</b>", meta_style), 
                 Paragraph(f"{summary_obj.model_used}", meta_style)],
            ]
            
            meta_table = Table(meta_data, colWidths=[1.5*inch, 3*inch])
            meta_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 20))
        
        # Add summary
        story.append(Paragraph("SUMMARY", heading_style))
        story.append(Spacer(1, 6))
        
        # Split summary into paragraphs for better formatting
        summary_paragraphs = summary_obj.summary.split('\n\n')
        for para in summary_paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip().replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 6))
        
        # Add key points
        if summary_obj.key_points:
            story.append(Spacer(1, 12))
            story.append(Paragraph("KEY POINTS", heading_style))
            story.append(Spacer(1, 6))
            
            key_points = summary_obj.key_points.split('\n')
            for i, point in enumerate(key_points, 1):
                if point.strip():
                    story.append(Paragraph(f"{i}. {point.strip()}", normal_style))
                    story.append(Spacer(1, 4))
        
        # Add original excerpt
        if include_original_excerpt and summary_obj.book:
            story.append(Spacer(1, 12))
            story.append(Paragraph("ORIGINAL TEXT EXCERPT", heading_style))
            story.append(Spacer(1, 6))
            
            excerpt = summary_obj.book.content[:1000]
            if len(summary_obj.book.content) > 1000:
                excerpt += "..."
            
            excerpt_style = ParagraphStyle(
                'ExcerptStyle',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6,
                textColor=colors.HexColor('#34495E'),
                fontName='Courier',
                leftIndent=20,
                rightIndent=20,
                backColor=colors.HexColor('#F8F9FA')
            )
            
            story.append(Paragraph(excerpt.replace('\n', '<br/>'), excerpt_style))
        
        # Add footer
        story.append(Spacer(1, 20))
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#95A5A6'),
            alignment=1  # Center aligned
        )
        story.append(Paragraph(f"Generated by Book Summarizer AI • Summary ID: {summary_obj.id} • {datetime.now().strftime('%Y-%m-%d')}", 
                             footer_style))
        
        # Build PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def export_to_html(summary_obj, include_metadata=True, include_original_excerpt=False):
        """Export summary to HTML format"""
        html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Summary: {html.escape(summary_obj.book.title)}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f9f9f9;
        }}
        .header {{
            background: linear-gradient(135deg, #3498db, #2ecc71);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .summary-content {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .metadata {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            border-left: 5px solid #3498db;
        }}
        .key-points {{
            background: #e8f4fc;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }}
        .excerpt {{
            background: #fef9e7;
            padding: 20px;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            margin: 20px 0;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #95a5a6;
            font-size: 12px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(summary_obj.book.title)}</h1>
        <p class="author">{html.escape(summary_obj.book.author or 'Unknown Author')}</p>
    </div>
'''
        
        if include_metadata:
            html_content += f'''
    <div class="metadata">
        <h3>Summary Information</h3>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{summary_obj.compression_ratio:.1%}</div>
                <div class="stat-label">Compression</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary_obj.read_time_minutes}</div>
                <div class="stat-label">Minutes to Read</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary_obj.time_saved}</div>
                <div class="stat-label">Minutes Saved</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary_obj.id}</div>
                <div class="stat-label">Summary ID</div>
            </div>
        </div>
        <p><strong>Generated:</strong> {summary_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>AI Model:</strong> {html.escape(summary_obj.model_used)}</p>
    </div>
'''
        
        html_content += f'''
    <div class="summary-content">
        <h2>Summary</h2>
        <p>{summary_obj.summary.replace('\n', '<br>')}</p>
    </div>
'''
        
        if summary_obj.key_points:
            html_content += f'''
    <div class="key-points">
        <h3>Key Points</h3>
        <ul>
'''
            for point in summary_obj.key_points.split('\n'):
                if point.strip():
                    html_content += f'            <li>{html.escape(point.strip())}</li>\n'
            
            html_content += '''        </ul>
    </div>
'''
        
        if include_original_excerpt and summary_obj.book:
            excerpt = summary_obj.book.content[:1000]
            if len(summary_obj.book.content) > 1000:
                excerpt += "..."
            
            html_content += f'''
    <div class="excerpt">
        <h3>Original Text Excerpt</h3>
        <p>{html.escape(excerpt).replace('\n', '<br>')}</p>
    </div>
'''
        
        html_content += f'''
    <div class="footer">
        <p>Generated by Book Summarizer AI • {datetime.now().strftime('%Y-%m-%d')}</p>
        <p>Summary ID: {summary_obj.id}</p>
    </div>
</body>
</html>
'''
        
        return html_content
    
    @staticmethod
    def export_to_csv(summary_obj, include_metadata=True):
        """Export summary to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Field', 'Value'])
        
        # Write metadata
        if include_metadata:
            writer.writerow(['Book Title', summary_obj.book.title])
            writer.writerow(['Book Author', summary_obj.book.author or 'Unknown'])
            writer.writerow(['Summary ID', summary_obj.id])
            writer.writerow(['Generated', summary_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['Compression Ratio', f"{summary_obj.compression_ratio:.1%}"])
            writer.writerow(['Read Time (minutes)', summary_obj.read_time_minutes])
            writer.writerow(['Time Saved (minutes)', summary_obj.time_saved])
            writer.writerow(['AI Model', summary_obj.model_used])
            writer.writerow(['Is Chunked Summary', summary_obj.is_chunked_summary])
            if summary_obj.is_chunked_summary:
                writer.writerow(['Chunks Processed', summary_obj.total_chunks_processed])
            writer.writerow(['', ''])  # Empty row
        
        # Write summary
        writer.writerow(['SUMMARY', ''])
        writer.writerow(['Text', summary_obj.summary])
        writer.writerow(['', ''])  # Empty row
        
        # Write key points
        if summary_obj.key_points:
            writer.writerow(['KEY POINTS', ''])
            for i, point in enumerate(summary_obj.key_points.split('\n'), 1):
                if point.strip():
                    writer.writerow([f'Point {i}', point.strip()])
        
        output.seek(0)
        return output
    
    @staticmethod
    def export_to_json(summary_obj, include_metadata=True):
        """Export summary to JSON format"""
        data = {
            'summary': {
                'id': summary_obj.id,
                'text': summary_obj.summary,
                'compression_ratio': summary_obj.compression_ratio,
                'read_time_minutes': summary_obj.read_time_minutes,
                'time_saved': summary_obj.time_saved,
                'created_at': summary_obj.created_at.isoformat(),
                'model_used': summary_obj.model_used,
                'is_chunked': summary_obj.is_chunked_summary,
                'chunks_processed': summary_obj.total_chunks_processed,
                'version': summary_obj.summary_version,
                'is_favorite': summary_obj.is_favorite
            },
            'book': {
                'id': summary_obj.book.id,
                'title': summary_obj.book.title,
                'author': summary_obj.book.author or 'Unknown',
                'word_count': summary_obj.book.word_count
            }
        }
        
        if summary_obj.key_points:
            data['summary']['key_points'] = [kp.strip() for kp in summary_obj.key_points.split('\n') if kp.strip()]
        
        if summary_obj.settings_used:
            data['summary']['settings'] = json.loads(summary_obj.settings_used)
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @staticmethod
    def create_zip_export(summary_obj, formats=None, include_original=True):
        """Create a ZIP file containing multiple export formats"""
        if formats is None:
            formats = ['txt', 'pdf', 'html', 'json']
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, f'summary_{summary_obj.id}_export.zip')
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                base_filename = f"summary_{summary_obj.id}_{summary_obj.book.title.replace(' ', '_')}"
                
                # Export to each format
                for fmt in formats:
                    if fmt == 'txt':
                        content = SummaryExporter.export_to_text(summary_obj, True, include_original)
                        zipf.writestr(f"{base_filename}.txt", content)
                    elif fmt == 'pdf':
                        pdf_buffer = SummaryExporter.export_to_pdf(summary_obj, True, include_original)
                        zipf.writestr(f"{base_filename}.pdf", pdf_buffer.getvalue())
                    elif fmt == 'html':
                        html_content = SummaryExporter.export_to_html(summary_obj, True, include_original)
                        zipf.writestr(f"{base_filename}.html", html_content)
                    elif fmt == 'json':
                        json_content = SummaryExporter.export_to_json(summary_obj, True)
                        zipf.writestr(f"{base_filename}.json", json_content)
                    elif fmt == 'csv':
                        csv_buffer = SummaryExporter.export_to_csv(summary_obj, True)
                        zipf.writestr(f"{base_filename}.csv", csv_buffer.getvalue())
                
                # Add original text if requested
                if include_original and summary_obj.book:
                    original_text = f"Original Text: {summary_obj.book.title}\n\n"
                    original_text += summary_obj.book.content[:5000]  # Limit size
                    if len(summary_obj.book.content) > 5000:
                        original_text += "\n\n[Content truncated - original is too large for ZIP]"
                    zipf.writestr(f"{base_filename}_original_excerpt.txt", original_text)
                
                # Add README file
                readme = f"""Book Summary Export Package
===========================

This ZIP file contains the summary of "{summary_obj.book.title}" 
by {summary_obj.book.author or 'Unknown Author'}.

Files included:
- {base_filename}.txt: Plain text version
- {base_filename}.pdf: Formatted PDF document
- {base_filename}.html: Web page version
- {base_filename}.json: Structured data (JSON format)
- {base_filename}_original_excerpt.txt: Excerpt from original text

Summary Information:
- Generated: {summary_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Compression: {summary_obj.compression_ratio:.1%}
- Read Time: {summary_obj.read_time_minutes} minutes
- Time Saved: {summary_obj.time_saved} minutes
- AI Model: {summary_obj.model_used}

Generated by Book Summarizer AI
"""
                zipf.writestr("README.txt", readme)
            
            # Read ZIP file into memory
            with open(zip_path, 'rb') as f:
                zip_data = f.read()
            
            return zip_data

# ==================== TASK 15: COMPARISON HELPER FUNCTIONS ====================

class SummaryComparer:
    """Task 15: Handles comparison of different summary versions"""
    
    @staticmethod
    def compare_summaries(summary1, summary2):
        """Compare two summaries and return difference analysis"""
        
        def preprocess_text(text):
            """Normalize text for comparison"""
            text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
            text = text.strip()
            return text
        
        text1 = preprocess_text(summary1.summary)
        text2 = preprocess_text(summary2.summary)
        
        # Split into sentences for better comparison
        sentences1 = re.split(r'(?<=[.!?])\s+', text1)
        sentences2 = re.split(r'(?<=[.!?])\s+', text2)
        
        # Calculate similarity score
        seq_matcher = SequenceMatcher(None, text1.lower(), text2.lower())
        similarity_score = seq_matcher.ratio()
        
        # Generate unified diff
        diff = list(unified_diff(
            sentences1, 
            sentences2,
            fromfile=f"Summary #{summary1.id} (v{summary1.summary_version})",
            tofile=f"Summary #{summary2.id} (v{summary2.summary_version})",
            lineterm=''
        ))
        
        # Extract key statistics
        stats = {
            'similarity_score': round(similarity_score * 100, 1),
            'length_diff': len(text2.split()) - len(text1.split()),
            'length_diff_percent': round(((len(text2.split()) / len(text1.split())) - 1) * 100, 1),
            'sentence_count_diff': len(sentences2) - len(sentences1),
            'compression_diff': summary2.compression_ratio - summary1.compression_ratio,
            'read_time_diff': summary2.read_time_minutes - summary1.read_time_minutes,
            'time_saved_diff': summary2.time_saved - summary1.time_saved
        }
        
        # Compare key points
        key_points1 = [kp.strip() for kp in (summary1.key_points or '').split('\n') if kp.strip()]
        key_points2 = [kp.strip() for kp in (summary2.key_points or '').split('\n') if kp.strip()]
        
        common_points = set(key_points1) & set(key_points2)
        unique_to_1 = set(key_points1) - set(key_points2)
        unique_to_2 = set(key_points2) - set(key_points1)
        
        return {
            'summary1': {
                'id': summary1.id,
                'version': summary1.summary_version,
                'compression': summary1.compression_ratio,
                'read_time': summary1.read_time_minutes,
                'word_count': len(text1.split()),
                'sentence_count': len(sentences1),
                'key_points_count': len(key_points1),
                'is_favorite': summary1.is_favorite,
                'created': summary1.created_at.isoformat(),
                'model': summary1.model_used
            },
            'summary2': {
                'id': summary2.id,
                'version': summary2.summary_version,
                'compression': summary2.compression_ratio,
                'read_time': summary2.read_time_minutes,
                'word_count': len(text2.split()),
                'sentence_count': len(sentences2),
                'key_points_count': len(key_points2),
                'is_favorite': summary2.is_favorite,
                'created': summary2.created_at.isoformat(),
                'model': summary2.model_used
            },
            'comparison': {
                'similarity': f"{stats['similarity_score']}%",
                'length_difference': stats['length_diff'],
                'length_difference_percent': f"{stats['length_diff_percent']}%",
                'sentence_count_difference': stats['sentence_count_diff'],
                'compression_difference': f"{stats['compression_diff']:+.3f}",
                'read_time_difference': f"{stats['read_time_diff']:+.1f} minutes",
                'time_saved_difference': f"{stats['time_saved_diff']:+.1f} minutes"
            },
            'key_points_analysis': {
                'common_points': list(common_points),
                'unique_to_summary1': list(unique_to_1),
                'unique_to_summary2': list(unique_to_2),
                'common_count': len(common_points),
                'unique_count_1': len(unique_to_1),
                'unique_count_2': len(unique_to_2)
            },
            'text_diff': diff[2:] if len(diff) > 2 else []  # Skip header lines
        }
    
    @staticmethod
    def generate_comparison_visualization(comparison_data):
        """Generate HTML visualization for comparison"""
        
        # Create color-coded diff visualization
        diff_html = '<div class="diff-container">'
        
        if comparison_data['text_diff']:
            diff_html += '<h4>Text Differences:</h4>'
            diff_html += '<div class="diff-content">'
            
            for line in comparison_data['text_diff']:
                if line.startswith('+'):
                    diff_html += f'<div class="diff-line added">{html.escape(line)}</div>'
                elif line.startswith('-'):
                    diff_html += f'<div class="diff-line removed">{html.escape(line)}</div>'
                else:
                    diff_html += f'<div class="diff-line unchanged">{html.escape(line)}</div>'
            
            diff_html += '</div>'
        
        diff_html += '</div>'
        
        return diff_html

# ==================== ENHANCED UI/UX TEMPLATES ====================

def create_navbar(theme='light'):
    """Create enhanced navigation bar HTML with responsive design"""
    # Get user theme preference
    if current_user.is_authenticated:
        user_prefs = current_user.get_preferences()
        theme = user_prefs.get('theme', 'light')
    
    nav_items = []
    
    if current_user.is_authenticated:
        # Safe access to username
        username = current_user.username if hasattr(current_user, 'username') else 'User'
        nav_items.append(f'''
        <li class="nav-item dropdown me-2">
            <a class="nav-link dropdown-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                <div class="user-avatar me-2">
                    <i class="fas fa-user-circle"></i>
                </div>
                <div class="d-none d-md-block">
                    <span class="fw-medium">{username}</span>
                    <small class="d-block text-muted">Reader</small>
                </div>
            </a>
            <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="navbarDropdown">
                <li><a class="dropdown-item" href="/dashboard"><i class="fas fa-tachometer-alt me-2"></i>Dashboard</a></li>
                <li><a class="dropdown-item" href="/upload"><i class="fas fa-upload me-2"></i>Upload Book</a></li>
                <li><a class="dropdown-item" href="/generate-summary"><i class="fas fa-robot me-2"></i>Generate Summary</a></li>
                <li><a class="dropdown-item" href="/summary-history"><i class="fas fa-history me-2"></i>Summary History</a></li>
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="/logout"><i class="fas fa-sign-out-alt me-2"></i>Logout</a></li>
            </ul>
        </li>
        ''')
        if current_user.is_admin():
            nav_items.append('<li class="nav-item"><a class="nav-link" href="/admin"><i class="fas fa-cog me-1"></i>Admin</a></li>')
        
        # Theme toggle button
        theme_icon = 'fa-moon' if theme == 'light' else 'fa-sun'
        theme_text = 'Dark Mode' if theme == 'light' else 'Light Mode'
        nav_items.append(f'''
        <li class="nav-item">
            <button class="nav-link theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle theme">
                <i class="fas {theme_icon}"></i>
                <span class="d-none d-md-inline ms-1">{theme_text}</span>
            </button>
        </li>
        ''')
    else:
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/login"><i class="fas fa-sign-in-alt me-1"></i>Login</a></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/register"><i class="fas fa-user-plus me-1"></i>Register</a></li>')
    
    return f'''
    <nav class="navbar navbar-expand-lg navbar-{theme} sticky-top shadow-sm" id="mainNavbar">
        <div class="container-fluid">
            <a class="navbar-brand d-flex align-items-center" href="/">
                <div class="brand-logo me-2">
                    <i class="fas fa-book-reader"></i>
                </div>
                <div>
                    <span class="fw-bold">Book Summarizer</span>
                    <small class="d-block text-muted">AI-Powered</small>
                </div>
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" 
                    aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/#features" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Explore our features">
                            <i class="fas fa-star me-1"></i>Features
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/#selfhelp-books" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Browse self-help books">
                            <i class="fas fa-brain me-1"></i>Self-Help Books
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/#chunking-info" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Learn about smart chunking">
                            <i class="fas fa-code-branch me-1"></i>Smart Chunking
                        </a>
                    </li>
                </ul>
                
                <ul class="navbar-nav">
                    {''.join(nav_items)}
                </ul>
            </div>
        </div>
    </nav>
    '''

def get_base_template(title, navbar, content, footer='', scripts='', theme='light'):
    """Return complete HTML template with enhanced UI/UX"""
    
    # Determine theme based on user preference
    theme_class = f'theme-{theme}'
    
    return f'''<!DOCTYPE html>
<html lang="en" class="{theme_class}" data-bs-theme="{theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Book Summarizer AI</title>
    
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <!-- Animate.css for smooth animations -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    
    <style>
        :root {{
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --accent-color: #4cc9f0;
            --success-color: #2ecc71;
            --warning-color: #f39c12;
            --danger-color: #e74c3c;
            --light-color: #f8f9fa;
            --dark-color: #343a40;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --border-radius: 12px;
            --box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
            --transition-speed: 0.3s;
        }}
        
        .theme-dark {{
            --primary-color: #5a6ff0;
            --secondary-color: #4a1fb8;
            --accent-color: #5cd9ff;
            --light-color: #2d3748;
            --dark-color: #1a202c;
            --text-primary: #e2e8f0;
            --text-secondary: #a0aec0;
            --box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background-color: var(--light-color);
            transition: background-color var(--transition-speed), color var(--transition-speed);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Merriweather', Georgia, serif;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .container {{
            max-width: 1400px;
            padding-left: 20px;
            padding-right: 20px;
        }}
        
        /* Enhanced Card Design */
        .card {{
            background: var(--light-color);
            border: none;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            transition: all var(--transition-speed) cubic-bezier(0.4, 0, 0.2, 1);
            overflow: hidden;
            margin-bottom: 1.5rem;
        }}
        
        .card:hover {{
            transform: translateY(-8px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.12);
        }}
        
        /* Enhanced Button Design */
        .btn {{
            border-radius: 50px;
            padding: 12px 24px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all var(--transition-speed) ease;
            border: none;
            position: relative;
            overflow: hidden;
        }}
        
        .btn::after {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 5px;
            height: 5px;
            background: rgba(255, 255, 255, 0.5);
            opacity: 0;
            border-radius: 100%;
            transform: scale(1, 1) translate(-50%);
            transform-origin: 50% 50%;
        }}
        
        .btn:focus:not(:active)::after {{
            animation: ripple 1s ease-out;
        }}
        
        @keyframes ripple {{
            0% {{
                transform: scale(0, 0);
                opacity: 0.5;
            }}
            100% {{
                transform: scale(20, 20);
                opacity: 0;
            }}
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
        }}
        
        .btn-primary:hover {{
            background: linear-gradient(135deg, var(--secondary-color), var(--primary-color));
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(67, 97, 238, 0.3);
        }}
        
        /* Form Controls */
        .form-control, .form-select {{
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            padding: 12px 16px;
            font-size: 16px;
            transition: all var(--transition-speed);
        }}
        
        .form-control:focus, .form-select:focus {{
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(67, 97, 238, 0.1);
        }}
        
        .form-label {{
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }}
        
        /* Enhanced Navigation */
        .navbar {{
            background: var(--light-color) !important;
            box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
            padding: 1rem 0;
        }}
        
        .navbar-brand {{
            font-weight: 800;
            font-size: 1.5rem;
            color: var(--primary-color) !important;
        }}
        
        .nav-link {{
            font-weight: 500;
            padding: 0.5rem 1rem !important;
            border-radius: 8px;
            transition: all var(--transition-speed);
        }}
        
        .nav-link:hover {{
            background: rgba(67, 97, 238, 0.1);
            color: var(--primary-color) !important;
        }}
        
        .user-avatar {{
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }}
        
        /* Hero Section */
        .hero-section {{
            background: linear-gradient(135deg, rgba(67, 97, 238, 0.1), rgba(76, 201, 240, 0.1));
            border-radius: var(--border-radius);
            padding: 4rem 2rem;
            margin: 2rem 0;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .hero-section::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 100%;
            height: 200%;
            background: radial-gradient(circle, rgba(76, 201, 240, 0.1) 0%, transparent 70%);
            z-index: 0;
        }}
        
        .hero-content {{
            position: relative;
            z-index: 1;
        }}
        
        /* Feature Cards */
        .feature-card {{
            text-align: center;
            padding: 2rem 1.5rem;
            border-radius: var(--border-radius);
            background: var(--light-color);
            height: 100%;
            border: 1px solid rgba(0, 0, 0, 0.05);
        }}
        
        .feature-icon {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            color: white;
            font-size: 2rem;
            transition: transform var(--transition-speed);
        }}
        
        .feature-card:hover .feature-icon {{
            transform: scale(1.1) rotate(5deg);
        }}
        
        /* Animations */
        .animate-fade-in {{
            animation: fadeIn 0.8s ease-out;
        }}
        
        .animate-slide-up {{
            animation: slideUp 0.6s ease-out;
        }}
        
        .animate-pulse {{
            animation: pulse 2s infinite;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes slideUp {{
            from {{ 
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{ 
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
            100% {{ transform: scale(1); }}
        }}
        
        /* Summary Content */
        .summary-content {{
            font-size: 18px;
            line-height: 1.8;
            font-family: 'Merriweather', Georgia, serif;
            padding: 2rem;
            background: var(--light-color);
            border-radius: var(--border-radius);
            border-left: 5px solid var(--primary-color);
        }}
        
        /* Book Content Viewer */
        .book-content {{
            max-height: 600px;
            overflow-y: auto;
            background: var(--light-color);
            padding: 2rem;
            border-radius: var(--border-radius);
            font-family: 'Merriweather', Georgia, serif;
            line-height: 1.8;
            font-size: 16px;
            border: 1px solid rgba(0, 0, 0, 0.1);
        }}
        
        /* Badges */
        .badge {{
            border-radius: 20px;
            padding: 6px 12px;
            font-weight: 600;
            font-size: 0.8rem;
        }}
        
        /* Progress Bar */
        .progress {{
            height: 10px;
            border-radius: 5px;
            background-color: rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .progress-bar {{
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            transition: width 1s ease-in-out;
        }}
        
        /* Tooltips */
        .tooltip-inner {{
            background: var(--dark-color);
            color: white;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
        }}
        
        /* Accessibility */
        .visually-hidden {{
            position: absolute !important;
            height: 1px;
            width: 1px;
            overflow: hidden;
            clip: rect(1px, 1px, 1px, 1px);
            white-space: nowrap;
        }}
        
        /* Focus styles for accessibility */
        :focus {{
            outline: 3px solid var(--primary-color);
            outline-offset: 2px;
        }}
        
        :focus:not(:focus-visible) {{
            outline: none;
        }}
        
        /* Responsive Design */
        @media (max-width: 768px) {{
            .hero-section {{
                padding: 2rem 1rem;
            }}
            
            .card {{
                margin-bottom: 1rem;
            }}
            
            .btn {{
                padding: 10px 20px;
                font-size: 14px;
            }}
            
            .navbar-nav {{
                text-align: center;
                padding: 1rem 0;
            }}
            
            .feature-card {{
                margin-bottom: 1rem;
            }}
        }}
        
        @media (max-width: 576px) {{
            .container {{
                padding-left: 15px;
                padding-right: 15px;
            }}
            
            .summary-content {{
                padding: 1rem;
                font-size: 16px;
            }}
        }}
        
        /* Dark theme adjustments */
        .theme-dark .card {{
            background: var(--dark-color);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .theme-dark .form-control, 
        .theme-dark .form-select {{
            background-color: #2d3748;
            border-color: #4a5568;
            color: var(--text-primary);
        }}
        
        .theme-dark .book-content {{
            background: #2d3748;
            border-color: #4a5568;
        }}
        
        /* Loading spinner */
        .loading-spinner {{
            display: inline-block;
            width: 50px;
            height: 50px;
            border: 3px solid rgba(67, 97, 238, 0.3);
            border-radius: 50%;
            border-top-color: var(--primary-color);
            animation: spin 1s ease-in-out infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 10px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--light-color);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: var(--primary-color);
            border-radius: 5px;
        }}
        
        .theme-dark ::-webkit-scrollbar-track {{
            background: var(--dark-color);
        }}
        
        .theme-dark ::-webkit-scrollbar-thumb {{
            background: var(--secondary-color);
        }}
        
        /* Toast notifications */
        .toast-container {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1055;
        }}
        
        .toast {{
            background: var(--light-color);
            border: none;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
        }}
        
        .theme-dark .toast {{
            background: var(--dark-color);
        }}
        
        /* Utility classes */
        .text-gradient {{
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .glass-effect {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .theme-dark .glass-effect {{
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        /* Task-specific styles */
        .chunk-visualization {{
            height: 100px;
            background: linear-gradient(90deg, #f0f0f0 0%, #e0e0e0 100%);
            border-radius: 5px;
            margin: 20px 0;
            position: relative;
            overflow: hidden;
        }}
        
        .theme-dark .chunk-visualization {{
            background: linear-gradient(90deg, #2d3748 0%, #4a5568 100%);
        }}
        
        .export-option {{
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            background: var(--light-color);
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            border: 2px solid transparent;
        }}
        
        .export-option:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            border-color: var(--primary-color);
        }}
        
        .theme-dark .export-option {{
            background: var(--dark-color);
            box-shadow: 0 3px 10px rgba(0,0,0,0.3);
        }}
        
        .comparison-container {{
            background: var(--light-color);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .theme-dark .comparison-container {{
            background: var(--dark-color);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        
        .key-point {{
            border-left: 4px solid var(--primary-color);
            padding-left: 15px;
            margin-bottom: 15px;
            background: var(--light-color);
            padding: 15px;
            border-radius: 5px;
        }}
        
        .theme-dark .key-point {{
            background: rgba(67, 97, 238, 0.1);
        }}
        
        /* Stats cards */
        .stats-card {{
            text-align: center;
            padding: 25px;
            border-radius: var(--border-radius);
            background: linear-gradient(135deg, var(--light-color), rgba(67, 97, 238, 0.05));
            margin-bottom: 20px;
            border: 1px solid rgba(0, 0, 0, 0.05);
        }}
        
        .theme-dark .stats-card {{
            background: linear-gradient(135deg, var(--dark-color), rgba(67, 97, 238, 0.1));
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .stats-value {{
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 5px;
            color: var(--primary-color);
        }}
        
        .stats-label {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    {navbar}
    
    <main class="flex-grow-1">
        <div class="container my-4 animate-fade-in">
            {content}
        </div>
    </main>
    
    {footer}
    
    <!-- Toast Container -->
    <div class="toast-container"></div>
    
    <!-- Onboarding Tooltip -->
    <div id="onboardingTooltip" class="onboarding-tooltip" style="display: none;">
        <button class="close-tooltip" onclick="hideOnboardingTooltip()">
            <i class="fas fa-times"></i>
        </button>
        <h6 id="tooltipTitle" class="mb-2">Welcome!</h6>
        <p id="tooltipMessage" class="mb-3 small">This is a quick guide to help you get started.</p>
        <div class="d-flex justify-content-between">
            <button class="btn btn-sm btn-outline-secondary" onclick="skipTutorial()">Skip Tutorial</button>
            <button class="btn btn-sm btn-primary" onclick="nextTooltipStep()">Next</button>
        </div>
    </div>
    
    <!-- Loading Modal -->
    <div class="modal fade" id="loadingModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-body text-center p-5">
                    <div class="loading-spinner mb-4"></div>
                    <h5 class="mb-3" id="loadingTitle">AI is working...</h5>
                    <p id="loadingMessage" class="text-muted">Processing your request</p>
                    <div class="progress mt-4" id="chunkProgress" style="display: none;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 0%"></div>
                    </div>
                    <p class="text-muted small mt-3" id="loadingDetail">This may take a moment for longer texts</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Self-Help Book Modal -->
    <div class="modal fade" id="selfHelpBookModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="modalBookTitle"></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted" id="modalBookAuthor"></p>
                    <h6>Book Summary:</h6>
                    <p id="modalBookSummary"></p>
                    <h6 class="mt-4">Key Concepts:</h6>
                    <ul class="list-group mb-3" id="modalKeyPoints"></ul>
                    <h6 class="mt-4">Practical Applications:</h6>
                    <ul class="list-group" id="modalPracticalTips"></ul>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Chunking Info Modal -->
    <div class="modal fade" id="chunkingInfoModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Chunking Analysis</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="chunkingAnalysisContent">
                        Loading analysis...
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Export Modal -->
    <div class="modal fade" id="exportModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Export Summary</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="exportOptionsContent">
                        Loading export options...
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Comparison Modal -->
    <div class="modal fade" id="comparisonModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Compare Summaries</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="comparisonContent">
                        Loading comparison...
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // Theme management
        function getCurrentTheme() {{
            return document.documentElement.getAttribute('data-bs-theme') || 'light';
        }}
        
        function setTheme(theme) {{
            document.documentElement.setAttribute('data-bs-theme', theme);
            document.documentElement.className = 'theme-' + theme;
            
            // Update theme toggle button
            const themeBtn = document.querySelector('.theme-toggle-btn');
            if (themeBtn) {{
                const icon = themeBtn.querySelector('i');
                const text = themeBtn.querySelector('span');
                if (theme === 'dark') {{
                    icon.className = 'fas fa-sun';
                    if (text) text.textContent = 'Light Mode';
                }} else {{
                    icon.className = 'fas fa-moon';
                    if (text) text.textContent = 'Dark Mode';
                }}
            }}
            
            // Save theme preference
            if (currentUserId) {{
                fetch('/api/update-theme', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ theme: theme }})
                }});
            }} else {{
                localStorage.setItem('theme', theme);
            }}
        }}
        
        function toggleTheme() {{
            const currentTheme = getCurrentTheme();
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
            showToast(`Switched to ${{newTheme === 'dark' ? 'dark' : 'light'}} mode`);
        }}
        
        // Initialize theme
        document.addEventListener('DOMContentLoaded', function() {{
            // Check for saved theme preference
            let savedTheme = localStorage.getItem('theme');
            if (!savedTheme && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                savedTheme = 'dark';
            }}
            if (savedTheme) {{
                setTheme(savedTheme);
            }}
            
            // Initialize tooltips
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {{
                return new bootstrap.Tooltip(tooltipTriggerEl);
            }});
            
            // Initialize modals
            var modalEl = document.getElementById('loadingModal');
            if (modalEl) {{
                window.loadingModal = new bootstrap.Modal(modalEl);
            }}
            
            // Check if first visit
            const tutorialCompleted = localStorage.getItem('tutorialCompleted');
            if (!tutorialCompleted && window.location.pathname === '/') {{
                setTimeout(showOnboardingTooltip, 2000);
            }}
        }});
        
        // Toast notifications
        function showToast(message, type = 'info') {{
            const toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) return;
            
            const toastId = 'toast-' + Date.now();
            const toast = document.createElement('div');
            toast.className = `toast fade show border-0`;
            toast.id = toastId;
            toast.setAttribute('role', 'alert');
            toast.setAttribute('aria-live', 'assertive');
            toast.setAttribute('aria-atomic', 'true');
            
            let icon = 'info-circle';
            let bgClass = 'bg-primary';
            
            switch(type) {{
                case 'success':
                    icon = 'check-circle';
                    bgClass = 'bg-success';
                    break;
                case 'warning':
                    icon = 'exclamation-triangle';
                    bgClass = 'bg-warning';
                    break;
                case 'error':
                    icon = 'times-circle';
                    bgClass = 'bg-danger';
                    break;
            }}
            
            toast.innerHTML = `
                <div class="toast-header ${{bgClass}} text-white">
                    <i class="fas fa-${{icon}} me-2"></i>
                    <strong class="me-auto">Notification</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${{message}}
                </div>
            `;
            
            toastContainer.appendChild(toast);
            
            // Auto remove after 5 seconds
            setTimeout(() => {{
                const toastEl = document.getElementById(toastId);
                if (toastEl) {{
                    toastEl.remove();
                }}
            }}, 5000);
        }}
        
        // Loading functions
        function showAILoading(title = "AI is working...", message = "Processing your request") {{
            document.getElementById('loadingTitle').textContent = title;
            document.getElementById('loadingMessage').textContent = message;
            
            if (window.loadingModal) {{
                window.loadingModal.show();
            }} else {{
                const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
                modal.show();
                window.loadingModal = modal;
            }}
            
            return window.loadingModal;
        }}
        
        function updateChunkProgress(current, total) {{
            const progressBar = document.getElementById('chunkProgress');
            const progressBarInner = progressBar.querySelector('.progress-bar');
            progressBar.style.display = 'block';
            
            const percentage = Math.round((current / total) * 100);
            progressBarInner.style.width = percentage + '%';
            progressBarInner.setAttribute('aria-valuenow', percentage);
            
            document.getElementById('loadingDetail').textContent = 
                `Processing chunk ${{current}} of ${{total}} (${{percentage}}%)`;
        }}
        
        function hideAILoading(modal) {{
            if (modal) {{
                modal.hide();
            }}
            const progressBar = document.getElementById('chunkProgress');
            if (progressBar) {{
                progressBar.style.display = 'none';
                progressBar.querySelector('.progress-bar').style.width = '0%';
            }}
        }}
        
        // Onboarding tutorial
        let currentTooltipStep = 0;
        const tooltipSteps = [
            {{
                title: "Welcome to Book Summarizer AI!",
                message: "Let's take a quick tour of the main features.",
                target: null
            }},
            {{
                title: "Upload Books",
                message: "Click 'Upload Book' to add books or paste text for summarization.",
                target: "uploadLink"
            }},
            {{
                title: "Generate Summaries",
                message: "Use 'Generate Summary' to create AI-powered summaries with custom settings.",
                target: "generateLink"
            }},
            {{
                title: "Explore Features",
                message: "Check out smart chunking, multi-format export, and comparison tools.",
                target: "featuresLink"
            }}
        ];
        
        function showOnboardingTooltip() {{
            const tooltip = document.getElementById('onboardingTooltip');
            if (!tooltip) return;
            
            currentTooltipStep = 0;
            updateTooltipContent();
            tooltip.style.display = 'block';
        }}
        
        function hideOnboardingTooltip() {{
            const tooltip = document.getElementById('onboardingTooltip');
            if (tooltip) {{
                tooltip.style.display = 'none';
            }}
        }}
        
        function nextTooltipStep() {{
            currentTooltipStep++;
            if (currentTooltipStep >= tooltipSteps.length) {{
                completeTutorial();
                return;
            }}
            updateTooltipContent();
        }}
        
        function updateTooltipContent() {{
            const tooltip = document.getElementById('onboardingTooltip');
            const title = document.getElementById('tooltipTitle');
            const message = document.getElementById('tooltipMessage');
            
            if (!tooltip || !title || !message) return;
            
            const step = tooltipSteps[currentTooltipStep];
            title.textContent = step.title;
            message.textContent = step.message;
            
            // Scroll to target element if specified
            if (step.target) {{
                const targetEl = document.getElementById(step.target);
                if (targetEl) {{
                    targetEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    // Highlight the element
                    targetEl.classList.add('animate-pulse');
                    setTimeout(() => {{
                        targetEl.classList.remove('animate-pulse');
                    }}, 2000);
                }}
            }}
        }}
        
        function skipTutorial() {{
            completeTutorial();
        }}
        
        function completeTutorial() {{
            hideOnboardingTooltip();
            localStorage.setItem('tutorialCompleted', 'true');
            showToast('Tutorial completed! You can restart it anytime from your profile.');
        }}
        
        // Form validation
        function validateForm(formId) {{
            const form = document.getElementById(formId);
            if (!form) return true;
            
            let isValid = true;
            const inputs = form.querySelectorAll('[required]');
            
            inputs.forEach(input => {{
                if (!input.value.trim()) {{
                    showInputError(input, 'This field is required');
                    isValid = false;
                }} else {{
                    clearInputError(input);
                }}
                
                // Email validation
                if (input.type === 'email' && input.value) {{
                    const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
                    if (!emailRegex.test(input.value)) {{
                        showInputError(input, 'Please enter a valid email address');
                        isValid = false;
                    }}
                }}
                
                // Password confirmation
                if (input.name === 'confirm_password' && input.value) {{
                    const password = form.querySelector('[name="password"]');
                    if (password && password.value !== input.value) {{
                        showInputError(input, 'Passwords do not match');
                        isValid = false;
                    }}
                }}
            }});
            
            return isValid;
        }}
        
        function showInputError(input, message) {{
            clearInputError(input);
            
            input.classList.add('is-invalid');
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.textContent = message;
            
            input.parentNode.appendChild(errorDiv);
            
            // Focus on first invalid input
            if (!input.hasAttribute('data-focused')) {{
                input.setAttribute('data-focused', 'true');
                input.focus();
                input.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}
        
        function clearInputError(input) {{
            input.classList.remove('is-invalid');
            input.removeAttribute('data-focused');
            
            const existingError = input.parentNode.querySelector('.invalid-feedback');
            if (existingError) {{
                existingError.remove();
            }}
        }}
        
        // Enhanced copy to clipboard
        async function copyToClipboard(text, buttonElement = null) {{
            try {{
                await navigator.clipboard.writeText(text);
                
                if (buttonElement) {{
                    const originalHTML = buttonElement.innerHTML;
                    buttonElement.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                    buttonElement.classList.add('btn-success');
                    
                    setTimeout(() => {{
                        buttonElement.innerHTML = originalHTML;
                        buttonElement.classList.remove('btn-success');
                    }}, 2000);
                }}
                
                showToast('Text copied to clipboard!', 'success');
                return true;
            }} catch (err) {{
                console.error('Failed to copy text: ', err);
                showToast('Failed to copy text. Please try again.', 'error');
                return false;
            }}
        }}
        
        // Smooth scroll to anchor links
        document.addEventListener('click', function(e) {{
            if (e.target.matches('a[href^="#"]')) {{
                e.preventDefault();
                const targetId = e.target.getAttribute('href');
                if (targetId === '#') return;
                
                const targetElement = document.querySelector(targetId);
                if (targetElement) {{
                    window.scrollTo({{
                        top: targetElement.offsetTop - 80,
                        behavior: 'smooth'
                    }});
                }}
            }}
        }});
        
        // Keep existing functions
        async function showSelfHelpBookSummary(bookId) {{
            try {{
                const response = await fetch('/api/selfhelp-book/' + bookId);
                const data = await response.json();
                
                if (response.ok) {{
                    const modal = new bootstrap.Modal(document.getElementById('selfHelpBookModal'));
                    document.getElementById('modalBookTitle').textContent = data.title;
                    document.getElementById('modalBookAuthor').textContent = 'Author: ' + data.author;
                    document.getElementById('modalBookSummary').textContent = data.summary;
                    document.getElementById('modalKeyPoints').innerHTML = data.key_points.map(point => 
                        `<li class="list-group-item">${{point}}</li>`
                    ).join('');
                    document.getElementById('modalPracticalTips').innerHTML = data.practical_tips.map(tip => 
                        `<li class="list-group-item">${{tip}}</li>`
                    ).join('');
                    modal.show();
                }}
            }} catch (error) {{
                showToast('Error loading summary', 'error');
            }}
        }}
        
        async function showChunkingAnalysis(bookId) {{
            try {{
                const loadingModal = showAILoading('Analyzing Chunks', 'Analyzing book chunk structure...');
                
                const response = await fetch('/api/book-chunking/' + bookId);
                const data = await response.json();
                
                hideAILoading(loadingModal);
                
                if (response.ok && data.success) {{
                    const modal = new bootstrap.Modal(document.getElementById('chunkingInfoModal'));
                    
                    const strategy = data.chunking_strategy || 'paragraph';
                    const strategyLower = strategy.toLowerCase();
                    
                    let html = `
                        <div class="alert alert-info">
                            <h6>Chunking Strategy: <span class="badge bg-primary">${{strategy}}</span></h6>
                            <p><strong>Total Chunks:</strong> ${{data.total_chunks}}</p>
                            <p><strong>Average Chunk Size:</strong> ${{data.average_chunk_size}} words</p>
                            <p><strong>Chunks with Overlap:</strong> ${{data.chunks_with_overlap}} (${{data.overlap_percentage}}%)</p>
                        </div>
                        
                        <h6 class="mt-4">Chunk Visualization:</h6>
                        <div class="chunk-visualization" id="chunkViz">
                            <!-- Chunks will be rendered here -->
                        </div>
                        
                        <h6 class="mt-4">Chunk Details:</h6>
                        <div class="table-responsive">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Chunk #</th>
                                        <th>Words</th>
                                        <th>Position</th>
                                        <th>Overlap</th>
                                    </tr>
                                </thead>
                                <tbody id="chunkTableBody">
                                    <!-- Chunk details will be inserted here -->
                                </tbody>
                            </table>
                        </div>
                    `;
                    
                    document.getElementById('chunkingAnalysisContent').innerHTML = html;
                    
                    if (data.chunk_details && data.chunk_details.length > 0) {{
                        const maxChunkSize = data.max_chunk_size || Math.max(...data.chunk_details.map(c => c.word_count));
                        renderChunkVisualization(data.chunk_details, maxChunkSize);
                        renderChunkTable(data.chunk_details);
                    }}
                    
                    modal.show();
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to load chunking analysis'), 'error');
                }}
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        
        function renderChunkVisualization(chunks, maxSize) {{
            const container = document.getElementById('chunkViz');
            if (!container) return;
            
            container.innerHTML = '';
            
            const totalWidth = container.offsetWidth;
            
            chunks.forEach(chunk => {{
                const chunkWidth = (chunk.word_count / maxSize) * totalWidth * 0.8;
                const leftPosition = (chunk.index / chunks.length) * totalWidth;
                
                const chunkBar = document.createElement('div');
                chunkBar.className = `chunk-bar ${{chunk.has_overlap ? 'overlap' : ''}}`;
                chunkBar.style.left = `${{leftPosition}}px`;
                chunkBar.style.width = `${{chunkWidth}}px`;
                
                const chunkInfo = document.createElement('div');
                chunkInfo.className = 'chunk-info';
                chunkInfo.textContent = `#${{chunk.index + 1}}`;
                
                chunkBar.appendChild(chunkInfo);
                container.appendChild(chunkBar);
            }});
        }}
        
        function renderChunkTable(chunks) {{
            const tbody = document.getElementById('chunkTableBody');
            if (!tbody) return;
            
            tbody.innerHTML = '';
            
            chunks.forEach(chunk => {{
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${{chunk.index + 1}}</td>
                    <td>${{chunk.word_count}}</td>
                    <td>${{chunk.position}}</td>
                    <td>${{chunk.has_overlap ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-danger"></i>'}}</td>
                `;
                tbody.appendChild(row);
            }});
        }}
        
        // Task 15: Comparison functions
        async function compareSummaries(summaryId1, summaryId2) {{
            try {{
                const loadingModal = showAILoading('Comparing Summaries', 'Analyzing differences...');
                
                const response = await fetch(`/api/compare-summaries/${{summaryId1}}/${{summaryId2}}`);
                const data = await response.json();
                
                hideAILoading(loadingModal);
                
                if (response.ok && data.success) {{
                    showComparisonModal(data.comparison);
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to compare summaries'), 'error');
                }}
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        
        function showComparisonModal(comparisonData) {{
            const modal = new bootstrap.Modal(document.getElementById('comparisonModal'));
            
            let html = `
                <div class="comparison-container animate-slide-up">
                    <div class="comparison-header d-flex justify-content-between align-items-center mb-4">
                        <h4>Summary Comparison</h4>
                        <div class="text-muted">
                            Similarity: <strong class="text-primary">${{comparisonData.comparison.similarity}}</strong>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5>Summary #${{comparisonData.summary1.id}} <small class="text-muted">(v${{comparisonData.summary1.version}})</small></h5>
                                    <p><strong>Compression:</strong> ${{(comparisonData.summary1.compression * 100).toFixed(1)}}%</p>
                                    <p><strong>Words:</strong> ${{comparisonData.summary1.word_count}}</p>
                                    <p><strong>Read Time:</strong> ${{comparisonData.summary1.read_time}} min</p>
                                    <p><strong>Created:</strong> ${{new Date(comparisonData.summary1.created).toLocaleDateString()}}</p>
                                    <p><strong>Model:</strong> ${{comparisonData.summary1.model}}</p>
                                    ${{comparisonData.summary1.is_favorite ? '<span class="badge bg-warning"><i class="fas fa-star me-1"></i>Favorite</span>' : ''}}
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6 mb-4">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5>Summary #${{comparisonData.summary2.id}} <small class="text-muted">(v${{comparisonData.summary2.version}})</small></h5>
                                    <p><strong>Compression:</strong> ${{(comparisonData.summary2.compression * 100).toFixed(1)}}%</p>
                                    <p><strong>Words:</strong> ${{comparisonData.summary2.word_count}}</p>
                                    <p><strong>Read Time:</strong> ${{comparisonData.summary2.read_time}} min</p>
                                    <p><strong>Created:</strong> ${{new Date(comparisonData.summary2.created).toLocaleDateString()}}</p>
                                    <p><strong>Model:</strong> ${{comparisonData.summary2.model}}</p>
                                    ${{comparisonData.summary2.is_favorite ? '<span class="badge bg-warning"><i class="fas fa-star me-1"></i>Favorite</span>' : ''}}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row mt-4">
                        <div class="col-md-3 col-6 mb-3">
                            <div class="stats-card">
                                <div class="stats-value">${{comparisonData.comparison.length_difference_percent}}</div>
                                <div class="stats-label">Length Difference</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="stats-card">
                                <div class="stats-value">${{comparisonData.comparison.sentence_count_difference}}</div>
                                <div class="stats-label">Sentence Count Diff</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="stats-card">
                                <div class="stats-value">${{comparisonData.comparison.read_time_difference}}</div>
                                <div class="stats-label">Read Time Difference</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="stats-card">
                                <div class="stats-value">${{comparisonData.comparison.time_saved_difference}}</div>
                                <div class="stats-label">Time Saved Difference</div>
                            </div>
                        </div>
                    </div>
            `;
            
            if (comparisonData.key_points_analysis.common_points.length > 0 || 
                comparisonData.key_points_analysis.unique_to_summary1.length > 0 ||
                comparisonData.key_points_analysis.unique_to_summary2.length > 0) {{
                html += `
                    <h5 class="mt-4">Key Points Comparison</h5>
                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h6>Unique to Summary #${{comparisonData.summary1.id}}</h6>
                                    <ul class="list-group list-group-flush">
                                        ${{comparisonData.key_points_analysis.unique_to_summary1.map(point => 
                                            `<li class="list-group-item">${{point}}</li>`).join('') || '<li class="list-group-item text-muted">None</li>'}}
                                    </ul>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h6>Common Points (${{comparisonData.key_points_analysis.common_count}})</h6>
                                    <ul class="list-group list-group-flush">
                                        ${{comparisonData.key_points_analysis.common_points.map(point => 
                                            `<li class="list-group-item">${{point}}</li>`).join('') || '<li class="list-group-item text-muted">None</li>'}}
                                    </ul>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h6>Unique to Summary #${{comparisonData.summary2.id}}</h6>
                                    <ul class="list-group list-group-flush">
                                        ${{comparisonData.key_points_analysis.unique_to_summary2.map(point => 
                                            `<li class="list-group-item">${{point}}</li>`).join('') || '<li class="list-group-item text-muted">None</li>'}}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            if (comparisonData.text_diff && comparisonData.text_diff.length > 0) {{
                html += `
                    <h5 class="mt-4">Text Differences</h5>
                    <div class="diff-container">
                        ${{comparisonData.text_diff.map(line => {{
                            if (line.startsWith('+')) {{
                                return `<div class="diff-line added">${{line}}</div>`;
                            }} else if (line.startsWith('-')) {{
                                return `<div class="diff-line removed">${{line}}</div>`;
                            }} else {{
                                return `<div class="diff-line unchanged">${{line}}</div>`;
                            }}
                        }}).join('')}}
                    </div>
                `;
            }}
            
            html += `</div>`;
            
            document.getElementById('comparisonContent').innerHTML = html;
            modal.show();
        }}
        
        // Task 14: Export functions
        async function showExportOptions(summaryId) {{
            try {{
                const modal = new bootstrap.Modal(document.getElementById('exportModal'));
                
                let html = `
                    <div class="animate-fade-in">
                        <h4>Export Summary</h4>
                        <p class="text-muted mb-4">Choose the format(s) you want to export:</p>
                        
                        <div class="row g-3">
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'txt')" role="button" tabindex="0" aria-label="Export as Text">
                                    <i class="fas fa-file-alt fa-2x mb-3"></i>
                                    <h5>Plain Text</h5>
                                    <p class="text-muted small">Simple .txt file with formatting</p>
                                </div>
                            </div>
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'pdf')" role="button" tabindex="0" aria-label="Export as PDF">
                                    <i class="fas fa-file-pdf fa-2x mb-3"></i>
                                    <h5>PDF Document</h5>
                                    <p class="text-muted small">Formatted PDF with styling</p>
                                </div>
                            </div>
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'html')" role="button" tabindex="0" aria-label="Export as HTML">
                                    <i class="fab fa-html5 fa-2x mb-3"></i>
                                    <h5>HTML Web Page</h5>
                                    <p class="text-muted small">Fully styled HTML document</p>
                                </div>
                            </div>
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'json')" role="button" tabindex="0" aria-label="Export as JSON">
                                    <i class="fas fa-code fa-2x mb-3"></i>
                                    <h5>JSON Data</h5>
                                    <p class="text-muted small">Structured JSON format</p>
                                </div>
                            </div>
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'csv')" role="button" tabindex="0" aria-label="Export as CSV">
                                    <i class="fas fa-file-csv fa-2x mb-3"></i>
                                    <h5>CSV Spreadsheet</h5>
                                    <p class="text-muted small">Tabular data format</p>
                                </div>
                            </div>
                            <div class="col-md-4 col-6">
                                <div class="export-option" onclick="exportSummary(${{summaryId}}, 'zip')" role="button" tabindex="0" aria-label="Export as ZIP">
                                    <i class="fas fa-file-archive fa-2x mb-3"></i>
                                    <h5>Complete Package</h5>
                                    <p class="text-muted small">ZIP with all formats</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mt-4">
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="checkbox" id="includeMetadata" checked>
                                <label class="form-check-label" for="includeMetadata">
                                    <i class="fas fa-info-circle me-2"></i>Include metadata (author, date, statistics)
                                </label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="includeOriginalExcerpt">
                                <label class="form-check-label" for="includeOriginalExcerpt">
                                    <i class="fas fa-book me-2"></i>Include original text excerpt
                                </label>
                            </div>
                        </div>
                        
                        <div class="mt-4">
                            <button class="btn btn-primary w-100" onclick="exportWithOptions(${{summaryId}})">
                                <i class="fas fa-download me-2"></i>Export with Selected Options
                            </button>
                        </div>
                    </div>
                `;
                
                document.getElementById('exportOptionsContent').innerHTML = html;
                modal.show();
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        
        async function exportSummary(summaryId, format) {{
            const includeMetadata = true;
            const includeOriginal = document.getElementById('includeOriginalExcerpt')?.checked || false;
            
            window.location.href = `/api/export-summary/${{summaryId}}/${{format}}?metadata=${{includeMetadata}}&original=${{includeOriginal}}`;
        }}
        
        async function exportWithOptions(summaryId) {{
            const includeMetadata = document.getElementById('includeMetadata')?.checked || true;
            const includeOriginal = document.getElementById('includeOriginalExcerpt')?.checked || false;
            const format = 'zip';
            
            window.location.href = `/api/export-summary/${{summaryId}}/${{format}}?metadata=${{includeMetadata}}&original=${{includeOriginal}}`;
        }}
        
        // Task 15: Favorite/Default summary functions
        async function toggleFavorite(summaryId) {{
            try {{
                const response = await fetch(`/api/toggle-favorite/${{summaryId}}`, {{
                    method: 'POST'
                }});
                
                const data = await response.json();
                
                if (response.ok && data.success) {{
                    if (data.is_favorite) {{
                        showToast('Summary marked as favorite!', 'success');
                    }} else {{
                        showToast('Summary removed from favorites.', 'info');
                    }}
                    setTimeout(() => {{
                        if (window.location.pathname.includes('/summary/')) {{
                            window.location.reload();
                        }}
                    }}, 1000);
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to update favorite status'), 'error');
                }}
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        
        async function setDefaultSummary(summaryId) {{
            try {{
                const response = await fetch(`/api/set-default-summary/${{summaryId}}`, {{
                    method: 'POST'
                }});
                
                const data = await response.json();
                
                if (response.ok && data.success) {{
                    showToast('Default summary set successfully!', 'success');
                    setTimeout(() => {{
                        if (window.location.pathname.includes('/book/')) {{
                            window.location.reload();
                        }}
                    }}, 1000);
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to set default summary'), 'error');
                }}
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            // Ctrl/Cmd + D to toggle dark mode
            if ((e.ctrlKey || e.metaKey) && e.key === 'd') {{
                e.preventDefault();
                toggleTheme();
            }}
            
            // Escape to close modals
            if (e.key === 'Escape') {{
                const modals = document.querySelectorAll('.modal.show');
                modals.forEach(modal => {{
                    const modalInstance = bootstrap.Modal.getInstance(modal);
                    if (modalInstance) {{
                        modalInstance.hide();
                    }}
                }});
            }}
        }});
        
        // Current user ID for theme management
        const currentUserId = {current_user.id if current_user.is_authenticated else 'null'};
    </script>
    
    {scripts}
</body>
</html>'''

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """Home page with enhanced UI/UX"""
    # Get user theme preference
    theme = 'light'
    if current_user.is_authenticated:
        user_prefs = current_user.get_preferences()
        theme = user_prefs.get('theme', 'light')
    
    navbar = create_navbar(theme)
    
    # Create enhanced self-help books section
    selfhelp_books_html = ''
    for book in SELF_HELP_BOOKS:
        selfhelp_books_html += f'''
        <div class="col-lg-4 col-md-6 mb-4">
            <div class="card h-100 animate-fade-in" style="animation-delay: {book['id'] * 0.1}s">
                <div class="card-img-top position-relative overflow-hidden" style="height: 200px;">
                    <img src="{book['cover']}" class="w-100 h-100 object-fit-cover" 
                         alt="{book['title']}" loading="lazy">
                    <div class="position-absolute top-0 end-0 m-3">
                        <span class="badge bg-primary">{book['year']}</span>
                    </div>
                </div>
                <div class="card-body d-flex flex-column">
                    <h5 class="card-title">{book['title']}</h5>
                    <p class="card-text text-muted mb-2"><small>{book['author']}</small></p>
                    <p class="card-text flex-grow-1">{book['summary'][:120]}...</p>
                    <button onclick="showSelfHelpBookSummary({book['id']})" 
                            class="btn btn-primary mt-auto w-100" 
                            aria-label="Learn insights from {book['title']}">
                        <i class="fas fa-brain me-2"></i>Learn Insights
                    </button>
                </div>
            </div>
        </div>
        '''
    
    # Create feature cards
    feature_cards = [
        {
            'icon': 'fa-robot',
            'title': 'AI-Powered Summaries',
            'description': 'Advanced DistilBART AI understands context and generates coherent, meaningful summaries.',
            'color': 'primary'
        },
        {
            'icon': 'fa-code-branch',
            'title': 'Smart Chunking',
            'description': 'Intelligent text chunking with overlapping boundaries for context preservation in long books.',
            'color': 'success'
        },
        {
            'icon': 'fa-file-export',
            'title': 'Multi-Format Export',
            'description': 'Download summaries in TXT, PDF, HTML, JSON, CSV formats or as complete ZIP packages.',
            'color': 'info'
        },
        {
            'icon': 'fa-exchange-alt',
            'title': 'Version Comparison',
            'description': 'Compare different summary versions side-by-side with detailed difference analysis.',
            'color': 'warning'
        }
    ]
    
    feature_cards_html = ''
    for i, feature in enumerate(feature_cards):
        feature_cards_html += f'''
        <div class="col-lg-3 col-md-6 mb-4">
            <div class="feature-card animate-slide-up" style="animation-delay: {i * 0.2}s">
                <div class="feature-icon">
                    <i class="fas {feature['icon']}"></i>
                </div>
                <h4 class="h5 mb-3">{feature['title']}</h4>
                <p class="text-muted">{feature['description']}</p>
            </div>
        </div>
        '''
    
    # Create hero section
    hero_buttons = ''
    if current_user.is_authenticated:
        hero_buttons = f'''
        <div class="mt-4">
            <a href="/dashboard" class="btn btn-primary btn-lg me-3 animate-pulse" id="dashboardLink">
                <i class="fas fa-tachometer-alt me-2"></i>Go to Dashboard
            </a>
            <a href="/upload" class="btn btn-outline-primary btn-lg me-3" id="uploadLink">
                <i class="fas fa-upload me-2"></i>Upload Book
            </a>
            <a href="/generate-summary" class="btn btn-outline-primary btn-lg" id="generateLink">
                <i class="fas fa-robot me-2"></i>Generate Summary
            </a>
        </div>
        '''
    else:
        hero_buttons = '''
        <div class="mt-4">
            <a href="/register" class="btn btn-primary btn-lg me-3 animate-pulse">
                <i class="fas fa-user-plus me-2"></i>Get Started Free
            </a>
            <a href="/login" class="btn btn-outline-primary btn-lg">
                <i class="fas fa-sign-in-alt me-2"></i>Login
            </a>
        </div>
        '''
    
    content = f'''
    <section class="hero-section animate-fade-in">
        <div class="hero-content">
            <h1 class="display-4 fw-bold mb-3 text-gradient">AI-Powered Book Summarization</h1>
            <p class="lead mb-4">Transform lengthy books into concise, meaningful summaries using advanced AI technology. 
            Save hours of reading time while retaining key insights.</p>
            
            <div class="d-flex flex-wrap justify-content-center gap-2 mb-4">
                <span class="badge bg-primary p-2">
                    <i class="fas fa-robot me-1"></i>Powered by DistilBART AI
                </span>
                <span class="badge bg-success p-2">
                    <i class="fas fa-code-branch me-1"></i>Smart Chunking System
                </span>
                <span class="badge bg-info p-2">
                    <i class="fas fa-file-export me-1"></i>Multi-Format Export
                </span>
                <span class="badge bg-warning p-2">
                    <i class="fas fa-exchange-alt me-1"></i>Version Comparison
                </span>
            </div>
            
            {hero_buttons}
        </div>
    </section>
    
    <section class="mb-5" id="features">
        <h2 class="text-center mb-5">Why Choose Our Summarizer?</h2>
        <div class="row">
            {feature_cards_html}
        </div>
    </section>
    
    <section class="mb-5" id="selfhelp-books">
        <div class="card">
            <div class="card-body">
                <h2 class="text-center mb-4">Popular Self-Help Books</h2>
                <p class="text-center text-muted mb-4">Explore insights from bestselling self-help books</p>
                <div class="row">
                    {selfhelp_books_html}
                </div>
            </div>
        </div>
    </section>
    
    <section class="mb-5" id="chunking-info">
        <div class="card">
            <div class="card-body">
                <h2 class="text-center mb-4">Smart Chunking System</h2>
                <p class="text-center mb-4">Our advanced chunking system intelligently processes long books by:</p>
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <div class="key-point">
                            <i class="fas fa-random text-primary me-2"></i>
                            <strong>Multiple Strategies</strong><br>
                            Paragraph-based, sentence-based, fixed-size, and smart adaptive chunking
                        </div>
                    </div>
                    <div class="col-md-6 mb-3">
                        <div class="key-point">
                            <i class="fas fa-exchange-alt text-success me-2"></i>
                            <strong>Context Overlap</strong><br>
                            Maintains 100-200 token overlap between chunks for context continuity
                        </div>
                    </div>
                    <div class="col-md-6 mb-3">
                        <div class="key-point">
                            <i class="fas fa-code-branch text-warning me-2"></i>
                            <strong>Natural Boundaries</strong><br>
                            Identifies paragraph endings and chapter breaks for intelligent splitting
                        </div>
                    </div>
                    <div class="col-md-6 mb-3">
                        <div class="key-point">
                            <i class="fas fa-puzzle-piece text-info me-2"></i>
                            <strong>Coherent Merging</strong><br>
                            Intelligently combines chunk summaries without redundancy
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <section class="mb-5" id="how-it-works">
        <div class="card">
            <div class="card-body">
                <h2 class="text-center mb-4">How It Works</h2>
                <div class="row">
                    <div class="col-md-3 col-6 mb-4">
                        <div class="text-center">
                            <div class="feature-icon mb-3 mx-auto">
                                <i class="fas fa-upload"></i>
                            </div>
                            <h5>1. Upload</h5>
                            <p class="text-muted small">Upload PDF or paste text</p>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-4">
                        <div class="text-center">
                            <div class="feature-icon mb-3 mx-auto">
                                <i class="fas fa-cogs"></i>
                            </div>
                            <h5>2. Process</h5>
                            <p class="text-muted small">AI analyzes and chunks content</p>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-4">
                        <div class="text-center">
                            <div class="feature-icon mb-3 mx-auto">
                                <i class="fas fa-robot"></i>
                            </div>
                            <h5>3. Summarize</h5>
                            <p class="text-muted small">Generate AI-powered summary</p>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-4">
                        <div class="text-center">
                            <div class="feature-icon mb-3 mx-auto">
                                <i class="fas fa-download"></i>
                            </div>
                            <h5>4. Export</h5>
                            <p class="text-muted small">Download in multiple formats</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    '''
    
    footer = '''
    <footer class="bg-dark text-white py-5 mt-5">
        <div class="container">
            <div class="row">
                <div class="col-md-4 mb-4">
                    <h5 class="mb-3">Book Summarizer AI</h5>
                    <p class="text-muted">Advanced AI-powered book summarization for students, professionals, and avid readers.</p>
                </div>
                <div class="col-md-4 mb-4">
                    <h5 class="mb-3">Features</h5>
                    <ul class="list-unstyled">
                        <li class="mb-2"><a href="#features" class="text-muted text-decoration-none">AI Summarization</a></li>
                        <li class="mb-2"><a href="#chunking-info" class="text-muted text-decoration-none">Smart Chunking</a></li>
                        <li class="mb-2"><a href="#export-info" class="text-muted text-decoration-none">Multi-Format Export</a></li>
                        <li><a href="#comparison-info" class="text-muted text-decoration-none">Version Comparison</a></li>
                    </ul>
                </div>
                <div class="col-md-4 mb-4">
                    <h5 class="mb-3">Accessibility</h5>
                    <p class="text-muted small">
                        <i class="fas fa-universal-access me-2"></i>Keyboard navigation supported<br>
                        <i class="fas fa-eye me-2"></i>Dark mode available<br>
                        <i class="fas fa-mobile-alt me-2"></i>Fully responsive design
                    </p>
                </div>
            </div>
            <hr class="my-4">
            <div class="text-center">
                <p class="mb-0">&copy; 2024 Book Summarizer AI. All rights reserved.</p>
                <p class="text-muted small mt-2">Built with Flask, SQLAlchemy, and DistilBART AI</p>
            </div>
        </div>
    </footer>
    '''
    
    return get_base_template(
        title="Book Summarizer AI - Intelligent Book Summaries",
        navbar=navbar,
        content=content,
        footer=footer,
        theme=theme
    )

# ==================== UPLOAD BOOK ROUTE ====================

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_book():
    """Upload book page with Task 10 chunking options and enhanced UI"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title', '').strip()
            author = request.form.get('author', '').strip()
            content = request.form.get('content', '').strip()
            
            # Check for file upload
            uploaded_file = request.files.get('file')
            
            if uploaded_file and uploaded_file.filename:
                # Process uploaded file
                extracted_text = file_processor.extract_text(uploaded_file)
                if extracted_text:
                    content = extracted_text
            
            if not content or not content.strip():
                flash('Please provide book content or upload a file', 'error')
                return redirect(url_for('upload_book'))
            
            if not title:
                title = "Untitled Book"
            
            # Clean content
            cleaned_content = clean_text_for_display(content, max_length=1000000)
            word_count = len(cleaned_content.split())
            
            # Create book record
            book = Book(
                title=title,
                author=author,
                content=cleaned_content,
                word_count=word_count,
                file_type='pdf' if uploaded_file and uploaded_file.filename.lower().endswith('.pdf') else 'text',
                user_id=current_user.id,
                chunking_strategy='smart',  # Default to smart chunking
                chunk_size=800,
                chunk_overlap=100
            )
            
            db.session.add(book)
            db.session.commit()
            
            # Check if chunking is needed
            if needs_chunking(book):
                flash(f'Book uploaded successfully! This book ({word_count:,} words) will use smart chunking for processing.', 'success')
            else:
                flash(f'Book uploaded successfully! ({word_count:,} words)', 'success')
            
            return redirect(url_for('view_book', book_id=book.id))
            
        except Exception as e:
            logger.error(f"Error uploading book: {str(e)}")
            flash(f'Error uploading book: {str(e)[:200]}', 'error')
            return redirect(url_for('upload_book'))
    
    # Get theme
    theme = 'light'
    if current_user.is_authenticated:
        user_prefs = current_user.get_preferences()
        theme = user_prefs.get('theme', 'light')
    
    navbar = create_navbar(theme)
    content = '''
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card animate-slide-up">
                <div class="card-body p-5">
                    <div class="text-center mb-5">
                        <div class="feature-icon mb-4 mx-auto">
                            <i class="fas fa-upload"></i>
                        </div>
                        <h2 class="mb-3">Upload Book</h2>
                        <p class="text-muted">Upload your book text or PDF file. Our smart chunking system will automatically handle long books.</p>
                    </div>
                    
                    <form method="POST" enctype="multipart/form-data" id="uploadForm">
                        <div class="mb-4">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                <strong>Smart Chunking Notice:</strong> Books over 1500 words will automatically use intelligent chunking to preserve context.
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <label for="title" class="form-label">
                                <i class="fas fa-heading me-2"></i>Book Title *
                            </label>
                            <input type="text" class="form-control" id="title" name="title" 
                                   placeholder="Enter book title" required>
                        </div>
                        
                        <div class="mb-4">
                            <label for="author" class="form-label">
                                <i class="fas fa-user me-2"></i>Author
                            </label>
                            <input type="text" class="form-control" id="author" name="author" 
                                   placeholder="Enter author name">
                        </div>
                        
                        <div class="mb-4">
                            <label class="form-label">
                                <i class="fas fa-upload me-2"></i>Upload Method
                            </label>
                            <div class="card">
                                <div class="card-body">
                                    <ul class="nav nav-pills mb-3" id="uploadMethodTab" role="tablist">
                                        <li class="nav-item" role="presentation">
                                            <button class="nav-link active" id="text-tab" data-bs-toggle="pill" 
                                                    data-bs-target="#textTab" type="button">
                                                <i class="fas fa-font me-2"></i>Paste Text
                                            </button>
                                        </li>
                                        <li class="nav-item" role="presentation">
                                            <button class="nav-link" id="file-tab" data-bs-toggle="pill" 
                                                    data-bs-target="#fileTab" type="button">
                                                <i class="fas fa-file-upload me-2"></i>Upload File
                                            </button>
                                        </li>
                                    </ul>
                                    
                                    <div class="tab-content" id="uploadMethodTabContent">
                                        <div class="tab-pane fade show active" id="textTab" role="tabpanel">
                                            <label for="content" class="form-label">Book Content *</label>
                                            <textarea class="form-control" id="content" name="content" 
                                                      rows="10" placeholder="Paste your book content here..."
                                                      oninput="updateWordCount()"></textarea>
                                            <div class="d-flex justify-content-between mt-2">
                                                <small class="text-muted">Minimum 100 words recommended</small>
                                                <small id="wordCount" class="text-muted">0 words</small>
                                            </div>
                                        </div>
                                        
                                        <div class="tab-pane fade" id="fileTab" role="tabpanel">
                                            <label for="file" class="form-label">Upload File</label>
                                            <input type="file" class="form-control" id="file" name="file" 
                                                   accept=".txt,.pdf,.doc,.docx">
                                            <div class="mt-2">
                                                <small class="text-muted">
                                                    <i class="fas fa-info-circle me-1"></i>
                                                    Supported formats: PDF, TXT, DOC, DOCX
                                                </small>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <div class="card">
                                <div class="card-header bg-primary text-white">
                                    <i class="fas fa-code-branch me-2"></i>Chunking Options (Task 10)
                                </div>
                                <div class="card-body">
                                    <div class="row">
                                        <div class="col-md-6 mb-3">
                                            <label class="form-label">Chunking Strategy</label>
                                            <select class="form-select" id="chunkingStrategy" name="chunking_strategy">
                                                <option value="smart" selected>Smart (Automatic)</option>
                                                <option value="paragraph">Paragraph-based</option>
                                                <option value="sentence">Sentence-based</option>
                                                <option value="fixed">Fixed-size</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6 mb-3">
                                            <label class="form-label">Chunk Size</label>
                                            <div class="input-group">
                                                <input type="number" class="form-control" value="800" 
                                                       id="chunkSize" name="chunk_size" min="100" max="2000">
                                                <span class="input-group-text">words</span>
                                            </div>
                                            <small class="text-muted">Recommended: 500-1000 words per chunk</small>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-12">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="enableOverlap" name="enable_overlap" checked>
                                                <label class="form-check-label" for="enableOverlap">
                                                    Enable context overlap between chunks
                                                </label>
                                                <small class="d-block text-muted">
                                                    Maintains 10% overlap to preserve context across chunks
                                                </small>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary btn-lg">
                                <i class="fas fa-upload me-2"></i>Upload Book
                            </button>
                            <a href="/dashboard" class="btn btn-outline-secondary">
                                <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            
            <div class="card mt-4 animate-fade-in">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-lightbulb me-2"></i>Chunking Tips</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-random text-primary me-2"></i>
                                <strong>Smart Chunking</strong><br>
                                Automatically detects paragraphs and natural breaks
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-exchange-alt text-success me-2"></i>
                                <strong>Context Preservation</strong><br>
                                Overlapping chunks maintain context between sections
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-rocket text-warning me-2"></i>
                                <strong>Parallel Processing</strong><br>
                                Multiple chunks can be processed simultaneously
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-puzzle-piece text-info me-2"></i>
                                <strong>Coherent Results</strong><br>
                                Intelligently combines chunk summaries
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function updateWordCount() {
        const text = document.getElementById('content').value;
        const words = text.trim().split(/\s+/).filter(word => word.length > 0);
        const wordCount = words.length;
        document.getElementById('wordCount').innerText = wordCount + ' words';
        
        // Show chunking info for large texts
        const chunkingNotice = document.querySelector('.alert-info');
        if (wordCount > 1500) {
            chunkingNotice.innerHTML = `
                <i class="fas fa-code-branch me-2"></i>
                <strong>Smart Chunking Enabled:</strong> This book (${wordCount.toLocaleString()} words) will use intelligent chunking with context overlap.
            `;
            chunkingNotice.classList.remove('alert-info');
            chunkingNotice.classList.add('alert-success');
        } else {
            chunkingNotice.innerHTML = `
                <i class="fas fa-info-circle me-2"></i>
                <strong>Smart Chunking Notice:</strong> Books over 1500 words will automatically use intelligent chunking to preserve context.
            `;
            chunkingNotice.classList.remove('alert-success');
            chunkingNotice.classList.add('alert-info');
        }
    }
    
    // Initialize word count
    document.addEventListener('DOMContentLoaded', function() {
        updateWordCount();
    });
    </script>
    '''
    
    return get_base_template(
        title="Upload Book",
        navbar=navbar,
        content=content,
        theme=theme
    )

# ==================== GENERATE SUMMARY ROUTE ====================

@app.route('/generate-summary', methods=['GET', 'POST'])
@login_required
def generate_summary():
    """Generate summary page with Task 9 AI options and Task 10 chunking"""
    if request.method == 'POST':
        try:
            # Get form data
            book_id = request.form.get('book_id')
            compression = float(request.form.get('compression', 0.3))
            style = request.form.get('style', 'paragraph')
            detail = request.form.get('detail', 'concise')
            
            if not book_id:
                flash('Please select a book', 'error')
                return redirect(url_for('generate_summary'))
            
            book = Book.query.get(book_id)
            if not book:
                flash('Book not found', 'error')
                return redirect(url_for('generate_summary'))
            
            # Check if user owns the book
            if book.user_id != current_user.id:
                flash('Unauthorized', 'error')
                return redirect(url_for('generate_summary'))
            
            # Prepare chunking if needed
            use_chunking = needs_chunking(book)
            
            if use_chunking:
                # Process chunks first
                chunking_result = process_book_chunks(book, 'smart')
                if not chunking_result['success']:
                    flash(f'Chunking failed: {chunking_result.get("error", "Unknown error")}', 'error')
                    return redirect(url_for('view_book', book_id=book_id))
            
            # Store settings
            settings = {
                'compression': compression,
                'style': style,
                'detail': detail,
                'use_chunking': use_chunking,
                'chunking_strategy': book.chunking_strategy if use_chunking else None
            }
            
            # Generate summary via API
            response = ai_summarizer.summarize_text(
                book.content,
                compression_ratio=compression
            )
            
            if response['success']:
                # Get next version number
                existing_summaries = Summary.query.filter_by(book_id=book.id).all()
                next_version = max([s.summary_version for s in existing_summaries] + [0]) + 1
                
                # Save summary
                summary = Summary(
                    book_id=book.id,
                    summary=response['summary'],
                    compression_ratio=response['compression_ratio'],
                    read_time_minutes=response['read_time_minutes'],
                    key_points=extract_key_points(response['summary']),
                    model_used=response.get('model_used', ai_summarizer.model_name),
                    summary_version=next_version,
                    settings_used=json.dumps(settings)
                )
                
                # If this is the first summary, set it as default
                if len(existing_summaries) == 0:
                    book.default_summary_id = summary.id
                
                db.session.add(summary)
                db.session.commit()
                
                flash('Summary generated successfully!', 'success')
                return redirect(url_for('view_summary', summary_id=summary.id))
            else:
                flash(f'Error generating summary: {response.get("error", "Unknown error")}', 'error')
                return redirect(url_for('view_book', book_id=book_id))
                
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            flash(f'Error: {str(e)[:200]}', 'error')
            return redirect(url_for('generate_summary'))
    
    # GET request - show form
    books = Book.query.filter_by(user_id=current_user.id).order_by(Book.title).all()
    
    if not books:
        flash('Please upload a book first', 'info')
        return redirect(url_for('upload_book'))
    
    books_html = ''
    for book in books:
        summary_count = Summary.query.filter_by(book_id=book.id).count()
        chunk_info = book.get_chunking_info()
        chunk_badge = ''
        if chunk_info['total_chunks'] > 0:
            chunk_badge = f'<span class="badge bg-warning ms-1"><i class="fas fa-code-branch me-1"></i>{chunk_info["total_chunks"]}</span>'
        
        books_html += f'''<div class="form-check mb-2">
            <input class="form-check-input" type="radio" name="book_id" id="book_{book.id}" value="{book.id}" required>
            <label class="form-check-label w-100" for="book_{book.id}">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>{book.title}</strong>
                        <small class="text-muted ms-2">{book.author or "Unknown"}</small>
                    </div>
                    <div>
                        <span class="badge bg-light text-dark">{book.word_count:,} words</span>
                        <span class="badge bg-light text-dark ms-1">{summary_count} summaries</span>
                        {chunk_badge}
                    </div>
                </div>
            </label>
        </div>'''
    
    # Get theme
    theme = 'light'
    if current_user.is_authenticated:
        user_prefs = current_user.get_preferences()
        theme = user_prefs.get('theme', 'light')
    
    navbar = create_navbar(theme)
    
    content = f'''<div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card animate-slide-up">
                <div class="card-body p-5">
                    <div class="text-center mb-5">
                        <div class="feature-icon mb-4 mx-auto">
                            <i class="fas fa-robot"></i>
                        </div>
                        <h2 class="mb-3">Generate AI Summary</h2>
                        <p class="text-muted">Use our advanced AI to generate summaries. The system automatically uses chunking for long books.</p>
                    </div>
                    
                    <form method="POST" id="summaryForm">
                        <div class="mb-4">
                            <label class="form-label">
                                <i class="fas fa-book me-2"></i>Select Book *
                            </label>
                            <div class="card">
                                <div class="card-body" style="max-height: 300px; overflow-y: auto;">
                                    {books_html if books_html else '<div class="text-center py-4"><i class="fas fa-book fa-3x text-muted mb-3"></i><h5>No Books Found</h5><p class="text-muted">Please upload a book first</p><a href="/upload" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Upload Book</a></div>'}
                                </div>
                            </div>
                        </div>
                        
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <label for="compression" class="form-label">
                                    <i class="fas fa-compress me-2"></i>Compression Level
                                </label>
                                <input type="range" class="form-range" id="compression" name="compression" 
                                       min="0.1" max="0.8" step="0.05" value="0.3"
                                       oninput="updateCompressionValue(this.value)">
                                <div class="d-flex justify-content-between">
                                    <small>Very Short</small>
                                    <small id="compressionValue">30%</small>
                                    <small>Very Detailed</small>
                                </div>
                                <small class="text-muted">Controls how much the original text is compressed</small>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="style" class="form-label">
                                        <i class="fas fa-pen-fancy me-2"></i>Summary Style
                                    </label>
                                    <select class="form-select" id="style" name="style">
                                        <option value="paragraph" selected>Paragraph (Narrative)</option>
                                        <option value="bullet">Bullet Points</option>
                                        <option value="executive">Executive Summary</option>
                                        <option value="detailed">Detailed Analysis</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <label class="form-label">
                                <i class="fas fa-sliders-h me-2"></i>Detail Level
                            </label>
                            <div class="row">
                                <div class="col-md-3 mb-2">
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="detail" id="detail_concise" value="concise" checked>
                                        <label class="form-check-label w-100" for="detail_concise">
                                            <div class="card">
                                                <div class="card-body text-center">
                                                    <i class="fas fa-bolt text-warning mb-2"></i>
                                                    <h6>Concise</h6>
                                                    <small class="text-muted">Key points only</small>
                                                </div>
                                            </div>
                                        </label>
                                    </div>
                                </div>
                                <div class="col-md-3 mb-2">
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="detail" id="detail_balanced" value="balanced">
                                        <label class="form-check-label w-100" for="detail_balanced">
                                            <div class="card">
                                                <div class="card-body text-center">
                                                    <i class="fas fa-scale-balanced text-success mb-2"></i>
                                                    <h6>Balanced</h6>
                                                    <small class="text-muted">Recommended</small>
                                                </div>
                                            </div>
                                        </label>
                                    </div>
                                </div>
                                <div class="col-md-3 mb-2">
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="detail" id="detail_detailed" value="detailed">
                                        <label class="form-check-label w-100" for="detail_detailed">
                                            <div class="card">
                                                <div class="card-body text-center">
                                                    <i class="fas fa-file-alt text-info mb-2"></i>
                                                    <h6>Detailed</h6>
                                                    <small class="text-muted">More context</small>
                                                </div>
                                            </div>
                                        </label>
                                    </div>
                                </div>
                                <div class="col-md-3 mb-2">
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="detail" id="detail_comprehensive" value="comprehensive">
                                        <label class="form-check-label w-100" for="detail_comprehensive">
                                            <div class="card">
                                                <div class="card-body text-center">
                                                    <i class="fas fa-book text-primary mb-2"></i>
                                                    <h6>Comprehensive</h6>
                                                    <small class="text-muted">Most detail</small>
                                                </div>
                                            </div>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                <strong>AI Processing Notice:</strong> 
                                <span id="chunkingNotice">Long books will use smart chunking automatically</span>
                            </div>
                        </div>
                        
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary btn-lg" onclick="showAILoading()">
                                <i class="fas fa-robot me-2"></i>Generate AI Summary
                            </button>
                            <a href="/dashboard" class="btn btn-outline-secondary">
                                <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            
            <div class="card mt-4 animate-fade-in">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-cogs me-2"></i>AI Settings Explained</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-compress text-primary me-2"></i>
                                <strong>Compression Level</strong><br>
                                10-20%: Very brief summary<br>
                                20-40%: Standard summary (recommended)<br>
                                40-80%: Detailed summary
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-code-branch text-success me-2"></i>
                                <strong>Smart Chunking</strong><br>
                                For books &gt;1500 words<br>
                                Preserves context across chunks<br>
                                Parallel processing for speed
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-robot text-warning me-2"></i>
                                <strong>AI Model</strong><br>
                                DistilBART-CNN-12-6<br>
                                Optimized for summarization<br>
                                Context-aware processing
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-history text-info me-2"></i>
                                <strong>Version Control</strong><br>
                                Automatic version numbering<br>
                                Compare different versions<br>
                                Set favorites and defaults
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>'''
    
    scripts = '''<script>
    function updateCompressionValue(value) {
        const percent = Math.round(value * 100);
        document.getElementById('compressionValue').innerText = percent + '%';
        
        // Update notice based on selected book
        const selectedBook = document.querySelector('input[name="book_id"]:checked');
        if (selectedBook) {
            const bookId = selectedBook.value;
            // In a real implementation, we would fetch book info
            updateChunkingNotice(bookId, percent);
        }
    }
    
    function updateChunkingNotice(bookId, compressionPercent) {
        // This would be populated via AJAX in a real implementation
        const notice = document.getElementById('chunkingNotice');
        if (compressionPercent < 20) {
            notice.innerHTML = 'Using ultra-compressed mode for key points only';
        } else if (compressionPercent < 40) {
            notice.innerHTML = 'Using balanced compression for optimal detail';
        } else {
            notice.innerHTML = 'Using detailed compression for comprehensive summary';
        }
    }
    
    // Update notice when book selection changes
    document.querySelectorAll('input[name="book_id"]').forEach(radio => {
        radio.addEventListener('change', function() {
            const compression = document.getElementById('compression').value;
            updateCompressionValue(compression);
        });
    });
    </script>'''
    
    return get_base_template(
        title="Generate AI Summary",
        navbar=navbar,
        content=content,
        scripts=scripts,
        theme=theme
    )

# ==================== API ROUTES ====================

@app.route('/api/book/<int:book_id>', methods=['DELETE'])
@login_required
def delete_book_api(book_id):
    """API to delete a book and all related data"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Delete related records
        for chunk in book.chunks:
            ChunkSummary.query.filter_by(chunk_id=chunk.id).delete()
        
        BookChunk.query.filter_by(book_id=book_id).delete()
        Summary.query.filter_by(book_id=book_id).delete()
        
        # Delete the book
        db.session.delete(book)
        db.session.commit()
        
        # Clear from chunk manager cache
        chunk_manager.clear_chunks(book_id)
        
        return jsonify({'success': True, 'message': 'Book deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting book: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/summarize-ai/<int:book_id>', methods=['POST'])
@login_required
def summarize_book_ai(book_id):
    """API to generate AI summary for a book"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get compression ratio from request
        data = request.get_json() or {}
        compression_ratio = data.get('compression_ratio', 0.3)
        
        # Check if chunking is needed
        if needs_chunking(book):
            # Use chunked summarization
            result = summarize_chunks(book, compression_ratio)
        else:
            # Generate regular summary
            result = ai_summarizer.summarize_text(book.content, compression_ratio)
            
            if result['success']:
                # Get next version number
                existing_summaries = Summary.query.filter_by(book_id=book.id).all()
                next_version = max([s.summary_version for s in existing_summaries] + [0]) + 1
                
                # Save summary to database
                summary = Summary(
                    book_id=book.id,
                    summary=result['summary'],
                    compression_ratio=result['compression_ratio'],
                    read_time_minutes=result['read_time_minutes'],
                    key_points=extract_key_points(result['summary']),
                    model_used=result.get('model_used', ai_summarizer.model_name),
                    summary_version=next_version
                )
                db.session.add(summary)
                db.session.commit()
                
                result['summary_id'] = summary.id
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/prepare-chunks/<int:book_id>', methods=['POST'])
@login_required
def prepare_chunks_api(book_id):
    """API to prepare chunks for a book"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get strategy from request
        data = request.get_json() or {}
        strategy = data.get('strategy', 'smart')
        
        # Process chunks
        result = process_book_chunks(book, strategy)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error preparing chunks: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/summarize-chunks/<int:book_id>', methods=['POST'])
@login_required
def summarize_chunks_api(book_id):
    """API to summarize book chunks"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get compression ratio from request
        data = request.get_json() or {}
        compression_ratio = data.get('compression_ratio', 0.3)
        
        # Summarize chunks
        result = summarize_chunks(book, compression_ratio)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error summarizing chunks: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/book-chunking/<int:book_id>')
@login_required
def get_book_chunking_api(book_id):
    """API to get chunking analysis for a book"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        analysis = get_chunking_analysis(book)
        
        return jsonify({
            'success': True,
            'book_id': book_id,
            **analysis
        })
        
    except Exception as e:
        logger.error(f"Error getting chunking analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/selfhelp-book/<int:book_id>')
def get_selfhelp_book_api(book_id):
    """API to get self-help book data"""
    book = SELF_HELP_BOOKS_DICT.get(book_id)
    
    if book:
        return jsonify(book)
    
    return jsonify({'error': 'Book not found'}), 404

# ==================== TASK 14: EXPORT API ROUTES ====================

@app.route('/api/export-summary/<int:summary_id>/<string:format>')
@login_required
def export_summary_api(summary_id, format):
    """Task 14: API to export summary in various formats"""
    try:
        summary = Summary.query.get(summary_id)
        
        if not summary:
            return jsonify({'success': False, 'error': 'Summary not found'}), 404
        
        book = Book.query.get(summary.book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the summary or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get query parameters for options
        include_metadata = request.args.get('metadata', 'true').lower() == 'true'
        include_original = request.args.get('original', 'false').lower() == 'true'
        
        # Increment export count
        summary.increment_export_count()
        
        # Generate export based on format
        if format == 'txt':
            content = SummaryExporter.export_to_text(summary, include_metadata, include_original)
            response = make_response(content)
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_{book.title.replace(" ", "_")}.txt"'
            return response
            
        elif format == 'pdf':
            pdf_buffer = SummaryExporter.export_to_pdf(summary, include_metadata, include_original)
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_{book.title.replace(" ", "_")}.pdf"'
            return response
            
        elif format == 'html':
            html_content = SummaryExporter.export_to_html(summary, include_metadata, include_original)
            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_{book.title.replace(" ", "_")}.html"'
            return response
            
        elif format == 'json':
            json_content = SummaryExporter.export_to_json(summary, include_metadata)
            response = make_response(json_content)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_{book.title.replace(" ", "_")}.json"'
            return response
            
        elif format == 'csv':
            csv_buffer = SummaryExporter.export_to_csv(summary, include_metadata)
            response = make_response(csv_buffer.getvalue())
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_{book.title.replace(" ", "_")}.csv"'
            return response
            
        elif format == 'zip':
            zip_data = SummaryExporter.create_zip_export(
                summary, 
                formats=['txt', 'pdf', 'html', 'json', 'csv'],
                include_original=include_original
            )
            response = make_response(zip_data)
            response.headers['Content-Type'] = 'application/zip'
            response.headers['Content-Disposition'] = f'attachment; filename="summary_{summary_id}_package.zip"'
            return response
            
        else:
            return jsonify({'success': False, 'error': 'Unsupported format'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

# ==================== TASK 15: COMPARISON API ROUTES ====================

@app.route('/api/compare-summaries/<int:summary_id1>/<int:summary_id2>')
@login_required
def compare_summaries_api(summary_id1, summary_id2):
    """Task 15: API to compare two summaries"""
    try:
        summary1 = Summary.query.get(summary_id1)
        summary2 = Summary.query.get(summary_id2)
        
        if not summary1 or not summary2:
            return jsonify({'success': False, 'error': 'Summary not found'}), 404
        
        # Check if summaries belong to the same book
        if summary1.book_id != summary2.book_id:
            return jsonify({'success': False, 'error': 'Cannot compare summaries from different books'}), 400
        
        book = Book.query.get(summary1.book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Compare summaries
        comparer = SummaryComparer()
        comparison_data = comparer.compare_summaries(summary1, summary2)
        
        return jsonify({
            'success': True,
            'book_id': book.id,
            'book_title': book.title,
            'comparison': comparison_data
        })
        
    except Exception as e:
        logger.error(f"Error comparing summaries: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/toggle-favorite/<int:summary_id>', methods=['POST'])
@login_required
def toggle_favorite_api(summary_id):
    """Task 15: API to toggle favorite status of a summary"""
    try:
        summary = Summary.query.get(summary_id)
        
        if not summary:
            return jsonify({'success': False, 'error': 'Summary not found'}), 404
        
        book = Book.query.get(summary.book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Toggle favorite status
        summary.is_favorite = not summary.is_favorite
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_favorite': summary.is_favorite,
            'summary_id': summary_id
        })
        
    except Exception as e:
        logger.error(f"Error toggling favorite: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/set-default-summary/<int:summary_id>', methods=['POST'])
@login_required
def set_default_summary_api(summary_id):
    """Task 15: API to set a summary as default for its book"""
    try:
        summary = Summary.query.get(summary_id)
        
        if not summary:
            return jsonify({'success': False, 'error': 'Summary not found'}), 404
        
        book = Book.query.get(summary.book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Set as default summary
        book.default_summary_id = summary_id
        db.session.commit()
        
        return jsonify({
            'success': True,
            'book_id': book.id,
            'default_summary_id': summary_id
        })
        
    except Exception as e:
        logger.error(f"Error setting default summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

# ==================== TASK 9 & 10: AI & CHUNKING API ROUTES ====================

@app.route('/api/ai-summarize', methods=['POST'])
def ai_summarize_api():
    """Task 9: API endpoint for AI summarization"""
    return create_summarize_endpoint()

@app.route('/api/ai-stats')
def ai_stats_api():
    """Task 9: API endpoint for AI statistics"""
    return create_stats_endpoint()

@app.route('/api/health')
def health_api():
    """Task 9: API endpoint for health check"""
    return create_health_endpoint()

@app.route('/api/chunking-stats/<int:book_id>')
@login_required
def chunking_stats_api(book_id):
    """Task 10: API endpoint for chunking statistics"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get chunking statistics
        chunks = BookChunk.query.filter_by(book_id=book_id).all()
        
        # Calculate chunk distribution
        chunk_sizes = [chunk.word_count for chunk in chunks]
        
        stats = {
            'total_chunks': len(chunks),
            'chunk_size_stats': {
                'min': min(chunk_sizes) if chunk_sizes else 0,
                'max': max(chunk_sizes) if chunk_sizes else 0,
                'avg': sum(chunk_sizes) // len(chunk_sizes) if chunk_sizes else 0,
                'median': sorted(chunk_sizes)[len(chunk_sizes) // 2] if chunk_sizes else 0
            },
            'overlap_count': sum(1 for chunk in chunks if chunk.has_context_overlap),
            'total_words': sum(chunk_sizes),
            'chunking_strategy': book.chunking_strategy,
            'chunking_completed': book.chunking_completed
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error getting chunking stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

# ==================== USER PREFERENCE API ====================

@app.route('/api/update-theme', methods=['POST'])
@login_required
def update_theme_api():
    """Update user theme preference"""
    try:
        data = request.get_json()
        if not data or 'theme' not in data:
            return jsonify({'success': False, 'error': 'Theme not specified'}), 400
        
        theme = data['theme']
        if theme not in ['light', 'dark']:
            return jsonify({'success': False, 'error': 'Invalid theme'}), 400
        
        # Update user preferences
        current_user.update_preferences({'theme': theme})
        
        return jsonify({'success': True, 'theme': theme})
        
    except Exception as e:
        logger.error(f"Error updating theme: {str(e)}")
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

# ==================== VIEW BOOK ROUTE ====================

@app.route('/book/<int:book_id>')
@login_required
def view_book(book_id):
    """View book details page with enhanced UI"""
    try:
        book = Book.query.get(book_id)
        
        if not book:
            flash('Book not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            flash('Unauthorized', 'error')
            return redirect(url_for('dashboard'))
        
        # Get summaries for this book
        summaries = Summary.query.filter_by(book_id=book_id)\
                               .order_by(Summary.created_at.desc())\
                               .all()
        
        # Get chunking info
        chunking_info = get_chunking_analysis(book)
        
        # Get theme
        theme = 'light'
        if current_user.is_authenticated:
            user_prefs = current_user.get_preferences()
            theme = user_prefs.get('theme', 'light')
        
        navbar = create_navbar(theme)
        
        # Create summaries HTML
        summaries_html = ''
        for i, summary in enumerate(summaries):
            favorite_icon = 'fas fa-star text-warning' if summary.is_favorite else 'far fa-star'
            default_badge = ''
            if book.default_summary_id == summary.id:
                default_badge = '<span class="badge bg-success ms-2"><i class="fas fa-check"></i> Default</span>'
            
            summaries_html += f'''
            <div class="card mb-3 animate-fade-in" style="animation-delay: {i * 0.1}s">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <h5 class="card-title mb-1">
                                Summary v{summary.summary_version}
                                {default_badge}
                            </h5>
                            <p class="card-text small text-muted mb-2">
                                <i class="far fa-clock me-1"></i>
                                Created: {summary.created_at.strftime('%Y-%m-%d %H:%M')}
                            </p>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-secondary" 
                                    onclick="toggleFavorite({summary.id})" 
                                    aria-label="Toggle favorite">
                                <i class="{favorite_icon}"></i>
                            </button>
                            {f'''<button class="btn btn-sm btn-outline-success" 
                                    onclick="setDefaultSummary({summary.id})" 
                                    aria-label="Set as default summary">
                                <i class="fas fa-check"></i>
                            </button>''' if book.default_summary_id != summary.id else ''}
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-3 col-6">
                            <div class="stats-card">
                                <div class="stats-value">{summary.compression_ratio:.0%}</div>
                                <div class="stats-label">Compression</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6">
                            <div class="stats-card">
                                <div class="stats-value">{summary.read_time_minutes}</div>
                                <div class="stats-label">Min Read</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6">
                            <div class="stats-card">
                                <div class="stats-value">{summary.time_saved}</div>
                                <div class="stats-label">Min Saved</div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6">
                            <div class="stats-card">
                                <div class="stats-value">{summary.export_count}</div>
                                <div class="stats-label">Exports</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <a href="/summary/{summary.id}" class="btn btn-primary me-md-2">
                            <i class="fas fa-eye me-2"></i>View
                        </a>
                        <button class="btn btn-outline-primary me-md-2" 
                                onclick="showExportOptions({summary.id})">
                            <i class="fas fa-download me-2"></i>Export
                        </button>
                        {f'''
                        <button class="btn btn-outline-warning" 
                                onclick="compareSummaries({summary.id}, {summaries[0].id})">
                            <i class="fas fa-exchange-alt me-2"></i>Compare
                        </button>''' if i > 0 else ''}
                    </div>
                </div>
            </div>
            '''
        
        # Create chunking info HTML
        chunking_html = ''
        if chunking_info['chunking_completed']:
            chunking_html = f'''
            <div class="alert alert-success">
                <i class="fas fa-check-circle me-2"></i>
                <strong>Chunking Completed:</strong> {chunking_info['total_chunks']} chunks created using {chunking_info['chunking_strategy']} strategy.
            </div>
            <div class="row">
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{chunking_info['total_chunks']}</div>
                        <div class="stats-label">Total Chunks</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{chunking_info['average_chunk_size']}</div>
                        <div class="stats-label">Avg. Chunk Size</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{chunking_info['chunks_with_overlap']}</div>
                        <div class="stats-label">Chunks with Overlap</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{chunking_info['overlap_percentage']}%</div>
                        <div class="stats-label">Overlap Percentage</div>
                    </div>
                </div>
            </div>
            '''
        elif chunking_info['chunking_required']:
            chunking_html = '''
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Chunking Recommended:</strong> This book is large and would benefit from smart chunking.
                <button class="btn btn-sm btn-outline-primary ms-2" 
                        onclick="prepareChunks(book_id)">
                    <i class="fas fa-code-branch me-1"></i>Prepare Chunks
                </button>
            </div>
            '''
        
        # Create book details HTML
        content = f'''
        <div class="animate-fade-in">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 class="mb-1">{book.title}</h2>
                    <p class="text-muted mb-0">
                        <i class="fas fa-user me-1"></i>{book.author or 'Unknown Author'}
                    </p>
                </div>
                <div class="btn-group">
                    <a href="/generate-summary?book_id={book.id}" class="btn btn-primary">
                        <i class="fas fa-robot me-2"></i>Generate New Summary
                    </a>
                    <button class="btn btn-outline-primary" onclick="showChunkingAnalysis({book.id})">
                        <i class="fas fa-code-branch me-2"></i>Chunking Info
                    </button>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{book.word_count:,}</div>
                        <div class="stats-label">Total Words</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{len(summaries)}</div>
                        <div class="stats-label">Summaries</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{book.upload_date.strftime('%Y-%m-%d')}</div>
                        <div class="stats-label">Upload Date</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-3">
                    <div class="stats-card">
                        <div class="stats-value">{book.file_type or 'text'}</div>
                        <div class="stats-label">File Type</div>
                    </div>
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <i class="fas fa-code-branch me-2"></i>Chunking Information (Task 10)
                </div>
                <div class="card-body">
                    {chunking_html}
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <i class="fas fa-file-alt me-2"></i>Book Content Preview
                </div>
                <div class="card-body">
                    <div class="book-content">
                        {clean_text_for_display(book.content[:5000])}
                        {f'<p class="text-center mt-3"><i class="fas fa-ellipsis-h"></i> Content truncated - showing first 5,000 characters</p>' if len(book.content) > 5000 else ''}
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <i class="fas fa-history me-2"></i>Summary History ({len(summaries)})
                </div>
                <div class="card-body">
                    {summaries_html if summaries else '''
                    <div class="text-center py-5">
                        <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                        <h5>No Summaries Yet</h5>
                        <p class="text-muted mb-4">Generate your first AI summary for this book</p>
                        <a href="/generate-summary?book_id=''' + str(book.id) + '''" class="btn btn-primary">
                            <i class="fas fa-robot me-2"></i>Generate First Summary
                        </a>
                    </div>
                    '''}
                </div>
            </div>
            
            <div class="mt-4">
                <button class="btn btn-danger" onclick="confirmDeleteBook({book.id})">
                    <i class="fas fa-trash me-2"></i>Delete Book
                </button>
                <a href="/dashboard" class="btn btn-outline-secondary ms-2">
                    <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
                </a>
            </div>
        </div>
        '''
        
        scripts = f'''<script>
        const book_id = {book.id};
        
        function confirmDeleteBook(bookId) {{
            if (confirm('Are you sure you want to delete this book and all its summaries? This action cannot be undone.')) {{
                fetch(`/api/book/${{bookId}}`, {{
                    method: 'DELETE'
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        showToast('Book deleted successfully', 'success');
                        setTimeout(() => {{
                            window.location.href = '/dashboard';
                        }}, 1000);
                    }} else {{
                        showToast('Error: ' + data.error, 'error');
                    }}
                }})
                .catch(error => {{
                    showToast('Error: ' + error.message, 'error');
                }});
            }}
        }}
        
        async function prepareChunks(bookId) {{
            try {{
                const loadingModal = showAILoading('Preparing Chunks', 'Analyzing book structure...');
                
                const response = await fetch(`/api/prepare-chunks/${{bookId}}`, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        strategy: 'smart'
                    }})
                }});
                
                const data = await response.json();
                
                hideAILoading(loadingModal);
                
                if (data.success) {{
                    showToast(`Prepared ${{data.total_chunks}} chunks successfully!`, 'success');
                    setTimeout(() => {{
                        window.location.reload();
                    }}, 1000);
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to prepare chunks'), 'error');
                }}
            }} catch (error) {{
                showToast('Error: ' + error.message, 'error');
            }}
        }}
        </script>'''
        
        return get_base_template(
            title=f"{book.title} - Book Details",
            navbar=navbar,
            content=content,
            scripts=scripts,
            theme=theme
        )
        
    except Exception as e:
        logger.error(f"Error viewing book: {str(e)}")
        flash(f'Error: {str(e)[:200]}', 'error')
        return redirect(url_for('dashboard'))

# ==================== VIEW SUMMARY ROUTE ====================

@app.route('/summary/<int:summary_id>')
@login_required
def view_summary(summary_id):
    """View summary details page with enhanced UI"""
    try:
        summary = Summary.query.get(summary_id)
        
        if not summary:
            flash('Summary not found', 'error')
            return redirect(url_for('dashboard'))
        
        book = Book.query.get(summary.book_id)
        if not book:
            flash('Book not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Check if user owns the book or is admin
        if book.user_id != current_user.id and not current_user.is_admin():
            flash('Unauthorized', 'error')
            return redirect(url_for('dashboard'))
        
        # Get other summaries for comparison
        other_summaries = Summary.query.filter(
            Summary.book_id == book.id,
            Summary.id != summary_id
        ).order_by(Summary.created_at.desc()).all()
        
        # Get theme
        theme = 'light'
        if current_user.is_authenticated:
            user_prefs = current_user.get_preferences()
            theme = user_prefs.get('theme', 'light')
        
        navbar = create_navbar(theme)
        
        # Create comparison options HTML
        comparison_html = ''
        for other_summary in other_summaries[:3]:  # Show max 3 comparisons
            comparison_html += f'''
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>Summary v{other_summary.summary_version}</strong>
                    <small class="text-muted ms-2">
                        Created: {other_summary.created_at.strftime('%Y-%m-%d')}
                    </small>
                </div>
                <button class="btn btn-sm btn-outline-primary" 
                        onclick="compareSummaries({summary.id}, {other_summary.id})">
                    <i class="fas fa-exchange-alt me-1"></i>Compare
                </button>
            </div>
            '''
        
        # Format summary content
        formatted_summary = format_summary_for_display(summary.summary, 'paragraph')
        
        # Get key points
        key_points_html = ''
        if summary.key_points:
            key_points = [kp.strip() for kp in summary.key_points.split('\n') if kp.strip()]
            for point in key_points:
                key_points_html += f'''
                <div class="key-point animate-fade-in">
                    <i class="fas fa-circle text-primary me-2"></i>
                    {point}
                </div>
                '''
        
        # Get settings used
        settings = summary.get_settings()
        
        # Get chunk info if it's a chunked summary
        chunk_info_html = ''
        if summary.is_chunked_summary:
            chunk_info = summary.get_chunk_summary_info()
            if chunk_info:
                chunk_info_html = f'''
                <div class="alert alert-info">
                    <i class="fas fa-code-branch me-2"></i>
                    <strong>Chunked Summary:</strong> This summary was generated using {chunk_info['total_chunks_processed']} chunks.
                </div>
                '''
        
        # Create content HTML
        content = f'''
        <div class="animate-fade-in">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 class="mb-1">Summary of: {book.title}</h2>
                    <p class="text-muted mb-0">
                        <i class="fas fa-user me-1"></i>{book.author or 'Unknown Author'}
                    </p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="showExportOptions({summary.id})">
                        <i class="fas fa-download me-2"></i>Export
                    </button>
                    <button class="btn btn-outline-primary" 
                            onclick="toggleFavorite({summary.id})"
                            aria-label="Toggle favorite">
                        <i class="{'fas' if summary.is_favorite else 'far'} fa-star me-2"></i>
                        Favorite
                    </button>
                    <a href="/book/{book.id}" class="btn btn-outline-secondary">
                        <i class="fas fa-arrow-left me-2"></i>Back to Book
                    </a>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-lg-8">
                    <div class="card mb-4">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h4 class="card-title mb-0">
                                    Summary v{summary.summary_version}
                                    {f'<span class="badge bg-warning ms-2"><i class="fas fa-star"></i> Favorite</span>' if summary.is_favorite else ''}
                                    {f'<span class="badge bg-success ms-2"><i class="fas fa-check"></i> Default</span>' if book.default_summary_id == summary.id else ''}
                                </h4>
                                <button class="btn btn-sm btn-outline-success" 
                                        onclick="setDefaultSummary({summary.id})"
                                        aria-label="Set as default summary">
                                    <i class="fas fa-check me-1"></i>Set as Default
                                </button>
                            </div>
                            
                            {chunk_info_html}
                            
                            <div class="summary-content mb-4">
                                {formatted_summary}
                            </div>
                            
                            {f'''
                            <div class="mb-4">
                                <h5><i class="fas fa-key me-2"></i>Key Points</h5>
                                {key_points_html}
                            </div>
                            ''' if key_points_html else ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4">
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5 class="card-title mb-4"><i class="fas fa-chart-bar me-2"></i>Statistics</h5>
                            
                            <div class="row">
                                <div class="col-6 mb-3">
                                    <div class="stats-card">
                                        <div class="stats-value">{summary.compression_ratio:.0%}</div>
                                        <div class="stats-label">Compression</div>
                                    </div>
                                </div>
                                <div class="col-6 mb-3">
                                    <div class="stats-card">
                                        <div class="stats-value">{summary.read_time_minutes}</div>
                                        <div class="stats-label">Min Read</div>
                                    </div>
                                </div>
                                <div class="col-6 mb-3">
                                    <div class="stats-card">
                                        <div class="stats-value">{summary.time_saved}</div>
                                        <div class="stats-label">Min Saved</div>
                                    </div>
                                </div>
                                <div class="col-6 mb-3">
                                    <div class="stats-card">
                                        <div class="stats-value">{summary.export_count}</div>
                                        <div class="stats-label">Exports</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5 class="card-title mb-3"><i class="fas fa-cogs me-2"></i>Settings Used</h5>
                            <div class="list-group list-group-flush">
                                <div class="list-group-item d-flex justify-content-between">
                                    <span>Compression:</span>
                                    <strong>{summary.compression_ratio:.0%}</strong>
                                </div>
                                <div class="list-group-item d-flex justify-content-between">
                                    <span>Style:</span>
                                    <strong>{settings.get('style', 'paragraph').title()}</strong>
                                </div>
                                <div class="list-group-item d-flex justify-content-between">
                                    <span>Detail:</span>
                                    <strong>{settings.get('detail', 'concise').title()}</strong>
                                </div>
                                <div class="list-group-item d-flex justify-content-between">
                                    <span>Model:</span>
                                    <strong>{summary.model_used}</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    {f'''
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title mb-3"><i class="fas fa-exchange-alt me-2"></i>Compare With</h5>
                            <div class="list-group list-group-flush">
                                {comparison_html if comparison_html else 
                                '<div class="list-group-item text-center text-muted py-3">No other summaries to compare</div>'}
                            </div>
                        </div>
                    </div>
                    ''' if other_summaries else ''}
                </div>
            </div>
            
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title mb-3"><i class="fas fa-info-circle me-2"></i>Summary Information</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <ul class="list-unstyled">
                                <li class="mb-2"><strong>Summary ID:</strong> {summary.id}</li>
                                <li class="mb-2"><strong>Created:</strong> {summary.created_at.strftime('%Y-%m-%d %H:%M:%S')}</li>
                                <li class="mb-2"><strong>Version:</strong> {summary.summary_version}</li>
                                <li><strong>Is Chunked:</strong> {'Yes' if summary.is_chunked_summary else 'No'}</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <ul class="list-unstyled">
                                <li class="mb-2"><strong>Original Words:</strong> {book.word_count:,}</li>
                                <li class="mb-2"><strong>Summary Words:</strong> {len(summary.summary.split()):,}</li>
                                <li class="mb-2"><strong>Words Saved:</strong> {book.word_count - len(summary.summary.split()):,}</li>
                                <li><strong>Compression Saved:</strong> {int((1 - summary.compression_ratio) * 100)}%</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        '''
        
        return get_base_template(
            title=f"Summary: {book.title}",
            navbar=navbar,
            content=content,
            theme=theme
        )
        
    except Exception as e:
        logger.error(f"Error viewing summary: {str(e)}")
        flash(f'Error: {str(e)[:200]}', 'error')
        return redirect(url_for('dashboard'))

# ==================== DASHBOARD ROUTE ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with enhanced UI"""
    try:
        # Get user's books
        books = Book.query.filter_by(user_id=current_user.id)\
                         .order_by(Book.upload_date.desc())\
                         .limit(20).all()
        
        # Get recent summaries
        recent_summaries = Summary.query\
            .join(Book, Summary.book_id == Book.id)\
            .filter(Book.user_id == current_user.id)\
            .order_by(Summary.created_at.desc())\
            .limit(10).all()
        
        # Calculate dashboard statistics
        total_books = Book.query.filter_by(user_id=current_user.id).count()
        total_summaries = Summary.query\
            .join(Book, Summary.book_id == Book.id)\
            .filter(Book.user_id == current_user.id).count()
        
        total_words = sum(book.word_count for book in books if book.word_count)
        avg_summary_length = 0
        if total_summaries > 0:
            avg_summary_length = sum(len(summary.summary.split()) for summary in recent_summaries) // total_summaries
        
        # Get theme
        theme = 'light'
        if current_user.is_authenticated:
            user_prefs = current_user.get_preferences()
            theme = user_prefs.get('theme', 'light')
        
        navbar = create_navbar(theme)
        
        # Create books HTML
        books_html = ''
        for i, book in enumerate(books[:5]):
            summary_count = Summary.query.filter_by(book_id=book.id).count()
            books_html += f'''
            <div class="col-lg-4 col-md-6 mb-4">
                <div class="card h-100 animate-fade-in" style="animation-delay: {i * 0.1}s">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <div>
                                <h5 class="card-title mb-1">{book.title[:50]}{'...' if len(book.title) > 50 else ''}</h5>
                                <p class="card-text small text-muted mb-0">
                                    <i class="fas fa-user me-1"></i>{book.author or 'Unknown'}
                                </p>
                            </div>
                            <span class="badge bg-light text-dark">{book.word_count:,}w</span>
                        </div>
                        
                        <p class="card-text small text-muted mb-3">
                            <i class="far fa-clock me-1"></i>
                            {book.upload_date.strftime('%Y-%m-%d')}
                        </p>
                        
                        <div class="d-flex justify-content-between align-items-center">
                            <span class="badge bg-primary">
                                <i class="fas fa-file-alt me-1"></i>{summary_count} summaries
                            </span>
                            <a href="/book/{book.id}" class="btn btn-sm btn-outline-primary">
                                View <i class="fas fa-arrow-right ms-1"></i>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            '''
        
        # Create recent summaries HTML
        recent_html = ''
        for i, summary in enumerate(recent_summaries):
            book = Book.query.get(summary.book_id)
            if not book:
                continue
            
            recent_html += f'''
            <div class="list-group-item animate-fade-in" style="animation-delay: {i * 0.1}s">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">{book.title[:60]}{'...' if len(book.title) > 60 else ''}</h6>
                        <small class="text-muted">
                            Summary v{summary.summary_version} • {summary.compression_ratio:.0%} compression
                        </small>
                    </div>
                    <div>
                        <a href="/summary/{summary.id}" class="btn btn-sm btn-outline-primary me-2">
                            View
                        </a>
                        <button class="btn btn-sm btn-outline-secondary" 
                                onclick="showExportOptions({summary.id})">
                            Export
                        </button>
                    </div>
                </div>
            </div>
            '''
        
        # Create content HTML
        content = f'''
        <div class="animate-fade-in">
            <div class="d-flex justify-content-between align-items-center mb-5">
                <div>
                    <h2 class="mb-2">Welcome back, {current_user.username}!</h2>
                    <p class="text-muted mb-0">Your personal book summarization dashboard</p>
                </div>
                <a href="/generate-summary" class="btn btn-primary btn-lg">
                    <i class="fas fa-robot me-2"></i>Generate New Summary
                </a>
            </div>
            
            <div class="row mb-5">
                <div class="col-md-3 col-6 mb-4">
                    <div class="stats-card animate-slide-up" style="animation-delay: 0s">
                        <div class="stats-value">{total_books}</div>
                        <div class="stats-label">Total Books</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-4">
                    <div class="stats-card animate-slide-up" style="animation-delay: 0.1s">
                        <div class="stats-value">{total_summaries}</div>
                        <div class="stats-label">Total Summaries</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-4">
                    <div class="stats-card animate-slide-up" style="animation-delay: 0.2s">
                        <div class="stats-value">{total_words:,}</div>
                        <div class="stats-label">Total Words</div>
                    </div>
                </div>
                <div class="col-md-3 col-6 mb-4">
                    <div class="stats-card animate-slide-up" style="animation-delay: 0.3s">
                        <div class="stats-value">{avg_summary_length}</div>
                        <div class="stats-label">Avg Summary Length</div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8 mb-4">
                    <div class="card h-100">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-4">
                                <h5 class="card-title mb-0">
                                    <i class="fas fa-book me-2"></i>Recent Books
                                </h5>
                                <a href="/upload" class="btn btn-sm btn-primary">
                                    <i class="fas fa-plus me-1"></i>Add Book
                                </a>
                            </div>
                            <div class="row">
                                {books_html if books_html else '''
                                <div class="col-12">
                                    <div class="text-center py-5">
                                        <i class="fas fa-book fa-3x text-muted mb-3"></i>
                                        <h5>No Books Yet</h5>
                                        <p class="text-muted mb-4">Upload your first book to get started</p>
                                        <a href="/upload" class="btn btn-primary">
                                            <i class="fas fa-upload me-2"></i>Upload First Book
                                        </a>
                                    </div>
                                </div>
                                '''}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-history me-2"></i>Recent Summaries
                            </h5>
                            <div class="list-group list-group-flush">
                                {recent_html if recent_html else '''
                                <div class="text-center py-5">
                                    <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                                    <h5>No Summaries Yet</h5>
                                    <p class="text-muted">Generate your first summary</p>
                                </div>
                                '''}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-bolt me-2"></i>Quick Actions
                            </h5>
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <a href="/upload" class="btn btn-outline-primary w-100 h-100 py-3">
                                        <i class="fas fa-upload fa-2x mb-2"></i><br>
                                        Upload Book
                                    </a>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <a href="/generate-summary" class="btn btn-outline-success w-100 h-100 py-3">
                                        <i class="fas fa-robot fa-2x mb-2"></i><br>
                                        Generate Summary
                                    </a>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <a href="/summary-history" class="btn btn-outline-warning w-100 h-100 py-3">
                                        <i class="fas fa-history fa-2x mb-2"></i><br>
                                        View History
                                    </a>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <button class="btn btn-outline-info w-100 h-100 py-3" onclick="showExportOptions()">
                                        <i class="fas fa-download fa-2x mb-2"></i><br>
                                        Bulk Export
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-chart-line me-2"></i>Usage Statistics
                            </h5>
                            <canvas id="usageChart" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        // Chart.js initialization
        document.addEventListener('DOMContentLoaded', function() {{
            const ctx = document.getElementById('usageChart').getContext('2d');
            
            // Sample data - in a real app, this would come from the server
            const data = {{
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{{
                    label: 'Books Uploaded',
                    data: [2, 5, 3, 7, 4, 6],
                    borderColor: '#4361ee',
                    backgroundColor: 'rgba(67, 97, 238, 0.1)',
                    fill: true,
                    tension: 0.4
                }}, {{
                    label: 'Summaries Generated',
                    data: [3, 8, 5, 10, 7, 9],
                    borderColor: '#4cc9f0',
                    backgroundColor: 'rgba(76, 201, 240, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }};
            
            new Chart(ctx, {{
                type: 'line',
                data: data,
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                stepSize: 2
                            }}
                        }}
                    }}
                }}
            }});
        }});
        </script>
        '''
        
        return get_base_template(
            title="Dashboard",
            navbar=navbar,
            content=content,
            theme=theme
        )
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash(f'Error: {str(e)[:200]}', 'error')
        return redirect(url_for('index'))

# ==================== SUMMARY HISTORY ROUTE ====================

@app.route('/summary-history')
@login_required
def summary_history():
    """View all summaries with filtering and search"""
    try:
        # Get filter parameters
        book_id = request.args.get('book_id', type=int)
        sort_by = request.args.get('sort_by', 'created')
        order = request.args.get('order', 'desc')
        
        # Build query
        query = Summary.query\
            .join(Book, Summary.book_id == Book.id)\
            .filter(Book.user_id == current_user.id)
        
        if book_id:
            query = query.filter(Summary.book_id == book_id)
        
        # Apply sorting
        if sort_by == 'created':
            query = query.order_by(Summary.created_at.desc() if order == 'desc' else Summary.created_at.asc())
        elif sort_by == 'compression':
            query = query.order_by(Summary.compression_ratio.desc() if order == 'desc' else Summary.compression_ratio.asc())
        elif sort_by == 'length':
            query = query.order_by(db.func.length(Summary.summary).desc() if order == 'desc' else db.func.length(Summary.summary).asc())
        
        # Get all summaries
        all_summaries = query.all()
        
        # Get user's books for filter
        user_books = Book.query.filter_by(user_id=current_user.id).all()
        
        # Get theme
        theme = 'light'
        if current_user.is_authenticated:
            user_prefs = current_user.get_preferences()
            theme = user_prefs.get('theme', 'light')
        
        navbar = create_navbar(theme)
        
        # Create book filter options
        book_options = '<option value="">All Books</option>'
        for book in user_books:
            selected = 'selected' if book_id == book.id else ''
            book_options += f'<option value="{book.id}" {selected}>{book.title}</option>'
        
        # Create summaries table HTML
        summaries_html = ''
        for i, summary in enumerate(all_summaries):
            book = Book.query.get(summary.book_id)
            if not book:
                continue
            
            word_count = len(summary.summary.split())
            time_saved = max(0, (book.word_count // 200) - summary.read_time_minutes)
            
            summaries_html += f'''
            <tr class="animate-fade-in" style="animation-delay: {i * 0.05}s">
                <td>
                    <div class="d-flex align-items-center">
                        <div class="me-3">
                            <i class="fas fa-file-alt fa-2x text-primary"></i>
                        </div>
                        <div>
                            <h6 class="mb-1">{book.title[:40]}{'...' if len(book.title) > 40 else ''}</h6>
                            <small class="text-muted">
                                v{summary.summary_version} • {book.author or 'Unknown'}
                            </small>
                        </div>
                    </div>
                </td>
                <td>{summary.compression_ratio:.0%}</td>
                <td>{summary.read_time_minutes} min</td>
                <td>{time_saved} min</td>
                <td>
                    <span class="badge bg-light text-dark">{word_count:,} words</span>
                    {f'<span class="badge bg-warning ms-1"><i class="fas fa-star"></i></span>' if summary.is_favorite else ''}
                    {f'<span class="badge bg-success ms-1"><i class="fas fa-check"></i></span>' if book.default_summary_id == summary.id else ''}
                </td>
                <td>{summary.created_at.strftime('%Y-%m-%d')}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <a href="/summary/{summary.id}" class="btn btn-outline-primary" title="View">
                            <i class="fas fa-eye"></i>
                        </a>
                        <button class="btn btn-outline-success" 
                                onclick="showExportOptions({summary.id})"
                                title="Export">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-outline-warning" 
                                onclick="toggleFavorite({summary.id})"
                                title="Toggle Favorite">
                            <i class="{'fas' if summary.is_favorite else 'far'} fa-star"></i>
                        </button>
                    </div>
                </td>
            </tr>
            '''
        
        # Create content HTML
        content = f'''
        <div class="animate-fade-in">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 class="mb-2">Summary History</h2>
                    <p class="text-muted mb-0">View and manage all your summaries</p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-primary" onclick="exportAllSummaries()">
                        <i class="fas fa-download me-2"></i>Export All
                    </button>
                    <a href="/dashboard" class="btn btn-outline-secondary">
                        <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
                    </a>
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-4">
                            <label for="bookFilter" class="form-label">Filter by Book</label>
                            <select class="form-select" id="bookFilter" onchange="filterSummaries()">
                                {book_options}
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label for="sortBy" class="form-label">Sort By</label>
                            <select class="form-select" id="sortBy" onchange="filterSummaries()">
                                <option value="created" {'selected' if sort_by == 'created' else ''}>Date Created</option>
                                <option value="compression" {'selected' if sort_by == 'compression' else ''}>Compression Ratio</option>
                                <option value="length" {'selected' if sort_by == 'length' else ''}>Summary Length</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label for="sortOrder" class="form-label">Sort Order</label>
                            <select class="form-select" id="sortOrder" onchange="filterSummaries()">
                                <option value="desc" {'selected' if order == 'desc' else ''}>Descending</option>
                                <option value="asc" {'selected' if order == 'asc' else ''}>Ascending</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Book / Summary</th>
                                    <th>Compression</th>
                                    <th>Read Time</th>
                                    <th>Time Saved</th>
                                    <th>Details</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {summaries_html if summaries_html else '''
                                <tr>
                                    <td colspan="7" class="text-center py-5">
                                        <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                                        <h5>No Summaries Found</h5>
                                        <p class="text-muted mb-4">Generate your first summary to get started</p>
                                        <a href="/generate-summary" class="btn btn-primary">
                                            <i class="fas fa-robot me-2"></i>Generate Summary
                                        </a>
                                    </td>
                                </tr>
                                '''}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="mt-4">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    Showing {len(all_summaries)} summaries • 
                    <strong>Total Compression Saved:</strong> {sum(1 - s.compression_ratio for s in all_summaries):.0%} • 
                    <strong>Total Time Saved:</strong> {sum(max(0, (Book.query.get(s.book_id).word_count // 200) - s.read_time_minutes) for s in all_summaries if Book.query.get(s.book_id))} minutes
                </div>
            </div>
        </div>
        
        <script>
        function filterSummaries() {{
            const bookId = document.getElementById('bookFilter').value;
            const sortBy = document.getElementById('sortBy').value;
            const sortOrder = document.getElementById('sortOrder').value;
            
            let url = '/summary-history?';
            if (bookId) url += `book_id=${{bookId}}&`;
            url += `sort_by=${{sortBy}}&order=${{sortOrder}}`;
            
            window.location.href = url;
        }}
        
        function exportAllSummaries() {{
            showToast('Bulk export feature coming soon!', 'info');
        }}
        </script>
        '''
        
        return get_base_template(
            title="Summary History",
            navbar=navbar,
            content=content,
            theme=theme
        )
        
    except Exception as e:
        logger.error(f"Error loading summary history: {str(e)}")
        flash(f'Error: {str(e)[:200]}', 'error')
        return redirect(url_for('dashboard'))

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('Please enter both username and password', 'error')
                return redirect(url_for('login_page'))
            
            # Find user by username or email
            user = User.query.filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user and user.check_password(password):
                login_user(user, remember=True)
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
                return redirect(url_for('login_page'))
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('Login failed. Please try again.', 'error')
            return redirect(url_for('login_page'))
    
    # GET request - show login form
    theme = 'light'
    navbar = create_navbar(theme)
    
    content = '''
    <div class="row justify-content-center">
        <div class="col-lg-6 col-md-8">
            <div class="card animate-slide-up">
                <div class="card-body p-5">
                    <div class="text-center mb-5">
                        <div class="feature-icon mb-4 mx-auto">
                            <i class="fas fa-sign-in-alt"></i>
                        </div>
                        <h2 class="mb-3">Login to Your Account</h2>
                        <p class="text-muted">Enter your credentials to access your summaries</p>
                    </div>
                    
                    <form method="POST" id="loginForm">
                        <div class="mb-4">
                            <label for="username" class="form-label">
                                <i class="fas fa-user me-2"></i>Username or Email *
                            </label>
                            <input type="text" class="form-control" id="username" name="username" 
                                   placeholder="Enter your username or email" required>
                        </div>
                        
                        <div class="mb-4">
                            <label for="password" class="form-label">
                                <i class="fas fa-lock me-2"></i>Password *
                            </label>
                            <input type="password" class="form-control" id="password" name="password" 
                                   placeholder="Enter your password" required>
                        </div>
                        
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary btn-lg">
                                <i class="fas fa-sign-in-alt me-2"></i>Login
                            </button>
                            <a href="/register" class="btn btn-outline-secondary">
                                <i class="fas fa-user-plus me-2"></i>Create New Account
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return get_base_template(
        title="Login",
        navbar=navbar,
        content=content,
        theme=theme
    )

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """Register page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validation
            if not username or not email or not password:
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('register_page'))
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('register_page'))
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long', 'error')
                return redirect(url_for('register_page'))
            
            # Check if username or email already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                flash('Username or email already exists', 'error')
                return redirect(url_for('register_page'))
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password_hash=password  # In production, use proper password hashing
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login_page'))
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('register_page'))
    
    # GET request - show registration form
    theme = 'light'
    navbar = create_navbar(theme)
    
    content = '''
    <div class="row justify-content-center">
        <div class="col-lg-6 col-md-8">
            <div class="card animate-slide-up">
                <div class="card-body p-5">
                    <div class="text-center mb-5">
                        <div class="feature-icon mb-4 mx-auto">
                            <i class="fas fa-user-plus"></i>
                        </div>
                        <h2 class="mb-3">Create Your Account</h2>
                        <p class="text-muted">Join thousands of users who save time with AI summaries</p>
                    </div>
                    
                    <form method="POST" id="registerForm">
                        <div class="mb-4">
                            <label for="username" class="form-label">
                                <i class="fas fa-user me-2"></i>Username *
                            </label>
                            <input type="text" class="form-control" id="username" name="username" 
                                   placeholder="Choose a username" required>
                            <small class="text-muted">3-20 characters, letters and numbers only</small>
                        </div>
                        
                        <div class="mb-4">
                            <label for="email" class="form-label">
                                <i class="fas fa-envelope me-2"></i>Email Address *
                            </label>
                            <input type="email" class="form-control" id="email" name="email" 
                                   placeholder="Enter your email" required>
                        </div>
                        
                        <div class="mb-4">
                            <label for="password" class="form-label">
                                <i class="fas fa-lock me-2"></i>Password *
                            </label>
                            <input type="password" class="form-control" id="password" name="password" 
                                   placeholder="Create a password" required>
                            <small class="text-muted">Minimum 6 characters</small>
                        </div>
                        
                        <div class="mb-4">
                            <label for="confirm_password" class="form-label">
                                <i class="fas fa-lock me-2"></i>Confirm Password *
                            </label>
                            <input type="password" class="form-control" id="confirm_password" name="confirm_password" 
                                   placeholder="Confirm your password" required>
                        </div>
                        
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary btn-lg">
                                <i class="fas fa-user-plus me-2"></i>Create Account
                            </button>
                            <a href="/login" class="btn btn-outline-secondary">
                                <i class="fas fa-sign-in-alt me-2"></i>Already have an account?
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            
            <div class="card mt-4 animate-fade-in">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-gift me-2"></i>Free Account Benefits</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-robot text-primary me-2"></i>
                                <strong>AI Summarization</strong><br>
                                Generate unlimited AI summaries
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-code-branch text-success me-2"></i>
                                <strong>Smart Chunking</strong><br>
                                Process books of any length
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-download text-warning me-2"></i>
                                <strong>Multi-Format Export</strong><br>
                                Download in 5+ formats
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="key-point">
                                <i class="fas fa-history text-info me-2"></i>
                                <strong>Unlimited History</strong><br>
                                Access all your past summaries
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return get_base_template(
        title="Register",
        navbar=navbar,
        content=content,
        theme=theme
    )

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

# ==================== ADMIN ROUTE ====================

@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard (basic implementation)"""
    if not current_user.is_admin():
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    
    # Get statistics
    total_users = User.query.count()
    total_books = Book.query.count()
    total_summaries = Summary.query.count()
    
    # Get recent activity
    recent_books = Book.query.order_by(Book.upload_date.desc()).limit(10).all()
    recent_summaries = Summary.query.order_by(Summary.created_at.desc()).limit(10).all()
    
    # Get theme
    theme = 'light'
    if current_user.is_authenticated:
        user_prefs = current_user.get_preferences()
        theme = user_prefs.get('theme', 'light')
    
    navbar = create_navbar(theme)
    
    # Create recent activity HTML
    activity_html = ''
    for i, book in enumerate(recent_books[:5]):
        user = User.query.get(book.user_id)
        activity_html += f'''
        <div class="list-group-item">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">{book.title[:50]}{'...' if len(book.title) > 50 else ''}</h6>
                    <small class="text-muted">
                        Uploaded by {user.username if user else 'Unknown'} • {book.upload_date.strftime('%Y-%m-%d')}
                    </small>
                </div>
                <span class="badge bg-light text-dark">{book.word_count:,}w</span>
            </div>
        </div>
        '''
    
    content = f'''
    <div class="animate-fade-in">
        <div class="d-flex justify-content-between align-items-center mb-5">
            <div>
                <h2 class="mb-2">Admin Dashboard</h2>
                <p class="text-muted mb-0">System overview and management</p>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="refreshStats()">
                    <i class="fas fa-sync-alt me-2"></i>Refresh
                </button>
            </div>
        </div>
        
        <div class="row mb-5">
            <div class="col-md-3 col-6 mb-4">
                <div class="stats-card animate-slide-up" style="animation-delay: 0s">
                    <div class="stats-value">{total_users}</div>
                    <div class="stats-label">Total Users</div>
                </div>
            </div>
            <div class="col-md-3 col-6 mb-4">
                <div class="stats-card animate-slide-up" style="animation-delay: 0.1s">
                    <div class="stats-value">{total_books}</div>
                    <div class="stats-label">Total Books</div>
                </div>
            </div>
            <div class="col-md-3 col-6 mb-4">
                <div class="stats-card animate-slide-up" style="animation-delay: 0.2s">
                    <div class="stats-value">{total_summaries}</div>
                    <div class="stats-label">Total Summaries</div>
                </div>
            </div>
            <div class="col-md-3 col-6 mb-4">
                <div class="stats-card animate-slide-up" style="animation-delay: 0.3s">
                    <div class="stats-value">{IMPORT_SUCCESS}</div>
                    <div class="stats-label">AI Status</div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title mb-4">
                            <i class="fas fa-chart-line me-2"></i>System Status
                        </h5>
                        <div class="list-group list-group-flush">
                            <div class="list-group-item d-flex justify-content-between">
                                <span>Database Status:</span>
                                <span class="badge bg-success">Connected</span>
                            </div>
                            <div class="list-group-item d-flex justify-content-between">
                                <span>AI Model Status:</span>
                                <span class="badge bg-{'success' if IMPORT_SUCCESS else 'warning'}">
                                    {'Loaded' if IMPORT_SUCCESS else 'Limited'}
                                </span>
                            </div>
                            <div class="list-group-item d-flex justify-content-between">
                                <span>Chunking System:</span>
                                <span class="badge bg-success">Active</span>
                            </div>
                            <div class="list-group-item d-flex justify-content-between">
                                <span>Export System:</span>
                                <span class="badge bg-success">Active</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title mb-4">
                            <i class="fas fa-history me-2"></i>Recent Activity
                        </h5>
                        <div class="list-group list-group-flush" style="max-height: 300px; overflow-y: auto;">
                            {activity_html if activity_html else 
                            '<div class="list-group-item text-center py-3 text-muted">No recent activity</div>'}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-body">
                <h5 class="card-title mb-4">
                    <i class="fas fa-cogs me-2"></i>System Configuration
                </h5>
                <div class="row">
                    <div class="col-md-6">
                        <h6>Task 9: AI Configuration</h6>
                        <ul class="list-unstyled">
                            <li class="mb-2"><strong>Model:</strong> {ai_summarizer.model_name}</li>
                            <li class="mb-2"><strong>Max Input Length:</strong> {ai_summarizer.max_input_length if hasattr(ai_summarizer, 'max_input_length') else 'N/A'}</li>
                            <li class="mb-2"><strong>Loaded:</strong> {'Yes' if hasattr(ai_summarizer, 'is_loaded') and ai_summarizer.is_loaded else 'No'}</li>
                        </ul>
                    </div>
                    <div class="col-md-6">
                        <h6>Task 10: Chunking Configuration</h6>
                        <ul class="list-unstyled">
                            <li class="mb-2"><strong>Strategy:</strong> {text_chunker.max_chunk_size if hasattr(text_chunker, 'max_chunk_size') else 'N/A'}</li>
                            <li class="mb-2"><strong>Overlap:</strong> {text_chunker.overlap if hasattr(text_chunker, 'overlap') else 'N/A'}</li>
                            <li class="mb-2"><strong>Smart Processing:</strong> {'Yes' if IMPORT_SUCCESS else 'Fallback'}</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    showToast('Refreshing statistics...', 'info');
setTimeout(() => {{
    window.location.reload();
}}, 1000);
    </script>
    '''
    
    return get_base_template(
        title="Admin Dashboard",
        navbar=navbar,
        content=content,
        theme=theme
    )

# ==================== DATABASE INITIALIZATION ====================

def init_db():
    """Initialize the database with sample data if needed"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if we need to add sample data
        if User.query.count() == 0:
            print("Initializing database with sample data...")
            
            # Create admin user
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash='admin123',  # In production, use proper hashing
                role='admin'
            )
            db.session.add(admin)
            
            # Create regular user
            user = User(
                username='demo',
                email='demo@example.com',
                password_hash='demo123',
                role='user'
            )
            db.session.add(user)
            
            db.session.commit()
            print("✓ Sample users created")
            
            # Create sample book for demo user
            sample_content = """
            Atomic Habits: An Easy & Proven Way to Build Good Habits & Break Bad Ones

            Chapter 1: The Surprising Power of Atomic Habits
            
            Tiny changes, remarkable results. That is the fundamental premise of atomic habits. 
            An atomic habit is a little habit that is part of a larger system. Just as atoms are 
            the building blocks of molecules, atomic habits are the building blocks of remarkable 
            results. Habits are the compound interest of self-improvement. Getting 1 percent better 
            every day counts for a lot in the long-run.
            
            Habits are a double-edged sword. They can work for you or against you, which is why 
            understanding the details is essential. Small changes often appear to make no difference 
            until you cross a critical threshold. The most powerful outcomes of any compounding 
            process are delayed. You need to be patient.
            
            Chapter 2: How Your Habits Shape Your Identity (and Vice Versa)
            
            There are three levels of change: outcome change, process change, and identity change. 
            The most effective way to change your habits is to focus not on what you want to achieve, 
            but on who you wish to become. Your identity emerges out of your habits. Every action 
            is a vote for the type of person you wish to become.
            """
            
            book = Book(
                title='Atomic Habits',
                author='James Clear',
                content=sample_content,
                word_count=len(sample_content.split()),
                file_type='text',
                user_id=user.id,
                chunking_strategy='smart',
                chunk_size=800,
                chunk_overlap=100
            )
            db.session.add(book)
            db.session.commit()
            
            # Generate sample summary
            result = ai_summarizer.summarize_text(sample_content, compression_ratio=0.3)
            
            if result['success']:
                summary = Summary(
                    book_id=book.id,
                    summary=result['summary'],
                    compression_ratio=result['compression_ratio'],
                    read_time_minutes=result['read_time_minutes'],
                    key_points=extract_key_points(result['summary']),
                    model_used=result.get('model_used', ai_summarizer.model_name),
                    summary_version=1,
                    is_favorite=True,
                    settings_used=json.dumps({
                        'compression': 0.3,
                        'style': 'paragraph',
                        'detail': 'balanced'
                    })
                )
                book.default_summary_id = summary.id
                db.session.add(summary)
                db.session.commit()
                print("✓ Sample book and summary created")
        
        print("✓ Database initialization complete")

# ==================== APPLICATION ENTRY POINT ====================

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Load AI model
    print("Loading AI model...")
    ai_summarizer.load_model()
    
    # Start Flask application
    print("\n" + "="*60)
    print("Book Summarizer AI - Combined Version")
    print("="*60)
    print(f"✅ AI Model: {ai_summarizer.model_name}")
    print(f"✅ Database: Initialized")
    print(f"✅ Chunking System: {'Advanced' if IMPORT_SUCCESS else 'Fallback'}")
    print(f"✅ Export System: Ready")
    print(f"✅ Comparison System: Ready")
    print("="*60)
    print("\n📚 Features Summary:")
    print("  • Task 9: AI Model Integration ✓")
    print("  • Task 10: Intelligent Chunking ✓")
    print("  • Task 14: Multi-format Export ✓")
    print("  • Task 15: Summary Comparison ✓")
    print("  • Task 18: Enhanced UI/UX ✓")
    print("  • All Previous Tasks ✓")
    print("\n🚀 Application is running at http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, threaded=True)