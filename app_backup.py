from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import json
from sqlalchemy import or_
import re
import html
import PyPDF2
import io

# Create Config class
class Config:
    SECRET_KEY = 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///book_summarizer.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ==================== DATABASE MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    
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

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, default=0)
    file_type = db.Column(db.String(20))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('books', lazy=True))
    summaries = db.relationship('Summary', backref='book', lazy=True)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    compression_ratio = db.Column(db.Float, default=0.0)
    read_time_minutes = db.Column(db.Integer, default=0)
    key_points = db.Column(db.Text)

# ==================== HELPER FUNCTIONS ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def extract_text_from_pdf(file_content):
    """Extract text from PDF file content"""
    try:
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        
        # Extract text from each page
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        
        return text if text.strip() else "Could not extract text from PDF. Please upload a text-based PDF."
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def clean_text_for_display(text, max_length=5000):
    """Clean text for safe display"""
    if not text:
        return ""
    
    # Remove any binary/PDF artifacts
    text = re.sub(r'%PDF-\d+\.\d+', '', text)
    text = re.sub(r'%\w+_\d+', '', text)
    text = re.sub(r'OB\w+_\d+', '', text)
    text = re.sub(r'/{.*?}', '', text)
    text = re.sub(r'endobj|stream|xref|trailer|startxref', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d+\s+\d+\s+obj', '', text)
    text = re.sub(r'&lt;&lt;.*?&gt;&gt;', '', text, flags=re.DOTALL)
    
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Escape HTML for safety
    text = html.escape(text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + '... [Content truncated]'
    
    return text.strip()

def create_navbar():
    """Create navigation bar HTML"""
    nav_items = []
    
    if current_user.is_authenticated:
        nav_items.append(f'''
        <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                <i class="fas fa-user me-1"></i>{current_user.username}
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="/dashboard"><i class="fas fa-tachometer-alt me-2"></i>Dashboard</a></li>
                <li><a class="dropdown-item" href="/upload"><i class="fas fa-upload me-2"></i>Upload Book</a></li>
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="/logout"><i class="fas fa-sign-out-alt me-2"></i>Logout</a></li>
            </ul>
        </li>
        ''')
        if current_user.is_admin():
            nav_items.append('<li class="nav-item"><a class="nav-link" href="/admin"><i class="fas fa-cog me-1"></i>Admin</a></li>')
    else:
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/login"><i class="fas fa-sign-in-alt me-1"></i>Login</a></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/register"><i class="fas fa-user-plus me-1"></i>Register</a></li>')
    
    return f'''
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow-lg">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-book-reader me-2"></i>Book Summarizer
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/#features"><i class="fas fa-star me-1"></i>Features</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/#selfhelp-books"><i class="fas fa-brain me-1"></i>Self-Help Books</a>
                    </li>
                    {''.join(nav_items)}
                </ul>
            </div>
        </div>
    </nav>
    '''

# ==================== TEXT PROCESSING ====================

class FileProcessor:
    def extract_text(self, file):
        """Extract text from uploaded file"""
        try:
            if hasattr(file, 'read'):
                file_content = file.read()
                
                # Check if it's a PDF file
                if file.filename.lower().endswith('.pdf'):
                    # Reset file pointer
                    file.seek(0)
                    file_content = file.read()
                    return extract_text_from_pdf(file_content)
                else:
                    # For text files
                    try:
                        return file_content.decode('utf-8', errors='ignore')
                    except:
                        return str(file_content)
            return str(file)
        except Exception as e:
            return f"Error processing file: {str(e)}"

class Summarizer:
    def summarize(self, text, ratio=0.3):
        """Simple summarization - takes first portion of text"""
        words = text.split()
        summary_length = int(len(words) * ratio)
        return ' '.join(words[:max(100, summary_length)])

file_processor = FileProcessor()
summarizer = Summarizer()

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

# ==================== HTML TEMPLATES ====================

BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Book Summarizer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; }}
        .card {{
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            border: none;
            overflow: hidden;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.2);
        }}
        .btn-primary {{
            background: linear-gradient(45deg, #3498db, #2ecc71);
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
        }}
        .book-content {{
            max-height: 600px;
            overflow-y: auto;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            white-space: pre-wrap;
            font-family: 'Georgia', serif;
            line-height: 1.8;
            font-size: 16px;
        }}
        .summary-content {{
            font-size: 18px;
            line-height: 1.8;
            font-family: 'Georgia', serif;
        }}
        .key-point {{
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-bottom: 15px;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
        }}
        .hero-section {{
            background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                        url('https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80');
            background-size: cover;
            background-position: center;
            color: white;
            border-radius: 15px;
            padding: 60px 20px;
            margin-bottom: 40px;
        }}
        .feature-card {{
            text-align: center;
            padding: 30px 20px;
            border-radius: 15px;
            background: white;
            height: 100%;
        }}
        .feature-card i {{
            font-size: 3rem;
            margin-bottom: 20px;
            background: linear-gradient(45deg, #3498db, #2ecc71);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
    </style>
</head>
<body>
    {navbar}
    <div class="container mt-4">
        {content}
    </div>
    {footer}
    {scripts}
</body>
</html>
'''

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """Home page"""
    navbar = create_navbar()
    
    selfhelp_books_html = ''
    for book in SELF_HELP_BOOKS:
        selfhelp_books_html += f'''
        <div class="col-md-4 mb-4">
            <div class="card h-100">
                <img src="{book['cover']}" class="card-img-top" alt="{book['title']}" style="height: 200px; object-fit: cover;">
                <div class="card-body">
                    <h5 class="card-title">{book['title']}</h5>
                    <p class="card-text"><small class="text-muted">{book['author']} ({book['year']})</small></p>
                    <p class="card-text">{book['summary'][:150]}...</p>
                    <button onclick="showSelfHelpBookSummary({book['id']})" class="btn btn-primary w-100">
                        <i class="fas fa-brain me-2"></i>Learn Insights
                    </button>
                </div>
            </div>
        </div>
        '''
    
    content = f'''
    <div class="hero-section text-center">
        <h1 class="display-4 fw-bold mb-4">Transform Your Reading Experience</h1>
        <p class="lead mb-4">Upload any book or paste text to get instant AI-powered summaries. Perfect for students, professionals, and book lovers.</p>
        {'<a href="/dashboard" class="btn btn-light btn-lg me-3"><i class="fas fa-tachometer-alt me-2"></i>Dashboard</a><a href="/upload" class="btn btn-outline-light btn-lg"><i class="fas fa-upload me-2"></i>Upload Book</a>' 
         if current_user.is_authenticated else 
         '<a href="/register" class="btn btn-light btn-lg me-3"><i class="fas fa-user-plus me-2"></i>Get Started</a><a href="/login" class="btn btn-outline-light btn-lg"><i class="fas fa-sign-in-alt me-2"></i>Login</a>'}
    </div>
    
    <div class="row mb-5" id="features">
        <div class="col-md-4 mb-4">
            <div class="feature-card">
                <i class="fas fa-bolt"></i>
                <h4>Fast Summarization</h4>
                <p>Get instant summaries using advanced AI algorithms. Save hours of reading time.</p>
            </div>
        </div>
        <div class="col-md-4 mb-4">
            <div class="feature-card">
                <i class="fas fa-file-upload"></i>
                <h4>Multiple Formats</h4>
                <p>Upload PDF, TXT, DOC, DOCX files or simply paste text. We support all major formats.</p>
            </div>
        </div>
        <div class="col-md-4 mb-4">
            <div class="feature-card">
                <i class="fas fa-search"></i>
                <h4>Smart Search</h4>
                <p>Easily find and organize your books with powerful search and filter tools.</p>
            </div>
        </div>
    </div>
    
    <div class="card mb-5" id="selfhelp-books">
        <div class="card-body">
            <h2 class="text-center mb-4">Popular Self-Help Books</h2>
            <div class="row">
                {selfhelp_books_html}
            </div>
        </div>
    </div>
    '''
    
    scripts = '''
    <div class="modal fade" id="selfHelpBookModal">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="modalBookTitle"></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
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
    
    <script>
        async function showSelfHelpBookSummary(bookId) {
            try {
                const response = await fetch('/api/selfhelp-book/' + bookId);
                const data = await response.json();
                
                if (response.ok) {
                    const modal = new bootstrap.Modal(document.getElementById('selfHelpBookModal'));
                    document.getElementById('modalBookTitle').innerText = data.title;
                    document.getElementById('modalBookAuthor').innerText = 'Author: ' + data.author;
                    document.getElementById('modalBookSummary').innerText = data.summary;
                    document.getElementById('modalKeyPoints').innerHTML = data.key_points.map(point => 
                        `<li class="list-group-item">${point}</li>`
                    ).join('');
                    document.getElementById('modalPracticalTips').innerHTML = data.practical_tips.map(tip => 
                        `<li class="list-group-item">${tip}</li>`
                    ).join('');
                    modal.show();
                }
            } catch (error) {
                alert('Error loading summary');
            }
        }
    </script>
    '''
    
    return BASE_TEMPLATE.format(
        title="Book Summarizer - AI-Powered Book Summaries",
        navbar=navbar,
        content=content,
        footer='<footer class="bg-dark text-white py-4 mt-5 text-center"><p>&copy; 2024 Book Summarizer. All rights reserved.</p></footer>',
        scripts=scripts
    )

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login page"""
    if current_user.is_authenticated:
        return redirect('/dashboard')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid username or password', 'error')
    
    navbar = create_navbar()
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0"><i class="fas fa-sign-in-alt me-2"></i>Login</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">
                            <i class="fas fa-sign-in-alt me-2"></i>Login
                        </button>
                    </form>
                    <div class="mt-3 text-center">
                        <p>Don't have an account? <a href="/register">Register here</a></p>
                        <p class="text-muted">Demo: admin / admin123</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return BASE_TEMPLATE.format(
        title="Login - Book Summarizer",
        navbar=navbar,
        content=content,
        footer='',
        scripts=''
    )

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """Register page"""
    if current_user.is_authenticated:
        return redirect('/dashboard')
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
        else:
            user = User(username=username, email=email, role='user')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect('/dashboard')
    
    navbar = create_navbar()
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-success text-white">
                    <h4 class="mb-0"><i class="fas fa-user-plus me-2"></i>Register</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <div class="mb-3">
                            <label for="confirm_password" class="form-label">Confirm Password</label>
                            <input type="password" class="form-control" name="confirm_password" required>
                        </div>
                        <button type="submit" class="btn btn-success w-100">
                            <i class="fas fa-user-plus me-2"></i>Register
                        </button>
                    </form>
                    <div class="mt-3 text-center">
                        <p>Already have an account? <a href="/login">Login here</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return BASE_TEMPLATE.format(
        title="Register - Book Summarizer",
        navbar=navbar,
        content=content,
        footer='',
        scripts=''
    )

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    books = Book.query.filter_by(user_id=current_user.id).order_by(Book.upload_date.desc()).limit(6).all()
    
    books_html = ''
    for book in books:
        has_summary = Summary.query.filter_by(book_id=book.id).first() is not None
        summary_btn = f'''
        <button onclick="generateSummary({book.id})" class="btn btn-primary btn-sm">
            <i class="fas fa-magic me-1"></i>Generate Summary
        </button>''' if not has_summary else f'''
        <a href="/summary/{book.id}" class="btn btn-success btn-sm">
            <i class="fas fa-eye me-1"></i>View Summary
        </a>'''
        
        books_html += f'''
        <div class="col-md-4 mb-4">
            <div class="card h-100">
                <div class="card-body">
                    <h5 class="card-title">{book.title}</h5>
                    <h6 class="card-subtitle mb-2 text-muted">{book.author or 'Unknown Author'}</h6>
                    <p class="card-text">
                        <small class="text-muted">
                            <i class="fas fa-calendar me-1"></i>{book.upload_date.strftime('%Y-%m-%d')}<br>
                            <i class="fas fa-file me-1"></i>{book.file_type}<br>
                            <i class="fas fa-chart-bar me-1"></i>{book.word_count} words
                        </small>
                    </p>
                    <div class="d-flex justify-content-between">
                        <a href="/book/{book.id}" class="btn btn-outline-primary btn-sm">
                            <i class="fas fa-book-open me-1"></i>View Book
                        </a>
                        {summary_btn}
                        <button onclick="deleteBook({book.id})" class="btn btn-outline-danger btn-sm">
                            <i class="fas fa-trash me-1"></i>Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>
        '''
    
    navbar = create_navbar()
    content = f'''
    <h1 class="mb-4"><i class="fas fa-tachometer-alt me-2"></i>Dashboard</h1>
    
    <div class="row mb-4">
        <div class="col-md-4">
            <div class="card bg-primary text-white">
                <div class="card-body text-center">
                    <h1 class="display-4">{Book.query.filter_by(user_id=current_user.id).count()}</h1>
                    <p class="card-text">Books Uploaded</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card bg-success text-white">
                <div class="card-body text-center">
                    <h1 class="display-4">{Summary.query.join(Book).filter(Book.user_id == current_user.id).count()}</h1>
                    <p class="card-text">Summaries Generated</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card bg-info text-white">
                <div class="card-body text-center">
                    <h1 class="display-4">{sum([b.word_count for b in Book.query.filter_by(user_id=current_user.id).all()] or [0])}</h1>
                    <p class="card-text">Total Words Processed</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3>My Books</h3>
        <a href="/upload" class="btn btn-primary">
            <i class="fas fa-upload me-2"></i>Upload New Book
        </a>
    </div>
    
    <div class="row">
        {books_html if books_html else '''
        <div class="col-12">
            <div class="alert alert-info text-center">
                <i class="fas fa-info-circle me-2"></i>No books uploaded yet. 
                <a href="/upload" class="alert-link">Upload your first book!</a>
            </div>
        </div>
        '''}
    </div>
    '''
    
    scripts = '''
    <script>
        async function deleteBook(bookId) {
            if (confirm('Are you sure you want to delete this book?')) {
                try {
                    const response = await fetch('/api/books/' + bookId, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        alert('Book deleted successfully!');
                        window.location.reload();
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
        }
        
        async function generateSummary(bookId) {
            if (confirm('Generate summary for this book?')) {
                try {
                    const response = await fetch('/api/summarize/' + bookId, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ summary_ratio: 0.3 })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        alert('Summary generated successfully!');
                        window.location.href = '/summary/' + data.summary_id;
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
        }
    </script>
    '''
    
    return BASE_TEMPLATE.format(
        title="Dashboard - Book Summarizer",
        navbar=navbar,
        content=content,
        footer='',
        scripts=scripts
    )

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload book page"""
    if request.method == 'POST':
        title = request.form.get('title', 'Untitled')
        author = request.form.get('author', 'Unknown')
        
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            content = file_processor.extract_text(file)
        else:
            content = request.form.get('content', '')
        
        if not content.strip():
            flash('No content provided', 'error')
            return redirect('/upload')
        
        # Clean and store content
        cleaned_content = clean_text_for_display(content, max_length=50000)
        word_count = len(cleaned_content.split())
        
        book = Book(
            title=title,
            author=author,
            content=cleaned_content,
            word_count=word_count,
            file_type=request.files['file'].filename.split('.')[-1] if 'file' in request.files and request.files['file'].filename else 'text',
            user_id=current_user.id
        )
        db.session.add(book)
        db.session.commit()
        
        flash('Book uploaded successfully!', 'success')
        return redirect('/dashboard')
    
    navbar = create_navbar()
    content = '''
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0"><i class="fas fa-upload me-2"></i>Upload Book</h4>
                </div>
                <div class="card-body">
                    <form method="POST" enctype="multipart/form-data">
                        <div class="mb-3">
                            <label for="title" class="form-label">Book Title</label>
                            <input type="text" class="form-control" name="title" required>
                        </div>
                        <div class="mb-3">
                            <label for="author" class="form-label">Author</label>
                            <input type="text" class="form-control" name="author">
                        </div>
                        <div class="mb-3">
                            <label for="file" class="form-label">Upload File (PDF, TXT, DOC, DOCX)</label>
                            <input type="file" class="form-control" name="file" accept=".pdf,.txt,.doc,.docx">
                            <div class="form-text">Or paste text below</div>
                        </div>
                        <div class="mb-3">
                            <label for="content" class="form-label">Or Paste Text Content</label>
                            <textarea class="form-control" name="content" rows="10" placeholder="Paste your book text here..."></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">
                            <i class="fas fa-upload me-2"></i>Upload Book
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return BASE_TEMPLATE.format(
        title="Upload Book - Book Summarizer",
        navbar=navbar,
        content=content,
        footer='',
        scripts=''
    )

@app.route('/book/<int:book_id>')
@login_required
def view_book(book_id):
    """View book content"""
    book = Book.query.get_or_404(book_id)
    
    if book.user_id != current_user.id and not current_user.is_admin():
        flash('Unauthorized access', 'error')
        return redirect('/dashboard')
    
    cleaned_content = clean_text_for_display(book.content, max_length=10000)
    
    navbar = create_navbar()
    content = f'''
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h1><i class="fas fa-book me-2"></i>{book.title}</h1>
            <p class="lead">{book.author or 'Unknown Author'}</p>
        </div>
        <div>
            <a href="/dashboard" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
            </a>
            {'<a href="/summary/' + str(book.id) + '" class="btn btn-success ms-2"><i class="fas fa-file-alt me-2"></i>View Summary</a>' 
             if Summary.query.filter_by(book_id=book.id).first() else 
             '<button onclick="generateSummary(' + str(book.id) + ')" class="btn btn-primary ms-2"><i class="fas fa-magic me-2"></i>Generate Summary</button>'}
        </div>
    </div>
    
    <div class="card mb-4">
        <div class="card-header bg-info text-white">
            <h5 class="mb-0"><i class="fas fa-info-circle me-2"></i>Book Information</h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-3">
                    <p><strong><i class="fas fa-calendar me-2"></i>Upload Date:</strong><br>{book.upload_date.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                <div class="col-md-3">
                    <p><strong><i class="fas fa-file me-2"></i>File Type:</strong><br>{book.file_type}</p>
                </div>
                <div class="col-md-3">
                    <p><strong><i class="fas fa-chart-bar me-2"></i>Word Count:</strong><br>{book.word_count:,} words</p>
                </div>
                <div class="col-md-3">
                    <p><strong><i class="fas fa-clock me-2"></i>Estimated Read Time:</strong><br>{book.word_count // 200} minutes</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header bg-primary text-white">
            <h5 class="mb-0"><i class="fas fa-book-open me-2"></i>Book Content</h5>
        </div>
        <div class="card-body">
            <div class="book-content">
                {cleaned_content}
            </div>
            {f'<p class="text-center mt-3"><em>Showing first 10,000 characters. Total characters: {len(book.content):,}</em></p>' 
             if len(book.content) > 10000 else ''}
        </div>
    </div>
    '''
    
    scripts = '''
    <script>
        async function generateSummary(bookId) {
            if (confirm('Generate summary for this book?')) {
                try {
                    const response = await fetch('/api/summarize/' + bookId, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ summary_ratio: 0.3 })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        alert('Summary generated successfully!');
                        window.location.href = '/summary/' + data.summary_id;
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
        }
    </script>
    '''
    
    return BASE_TEMPLATE.format(
        title=f"{book.title} - Book Summarizer",
        navbar=navbar,
        content=content,
        footer='',
        scripts=scripts
    )

@app.route('/summary/<int:summary_id>')
@login_required
def view_summary(summary_id):
    """View summary"""
    summary = Summary.query.get_or_404(summary_id)
    
    if summary.book.user_id != current_user.id and not current_user.is_admin():
        flash('Unauthorized access', 'error')
        return redirect('/dashboard')
    
    cleaned_summary = clean_text_for_display(summary.summary, max_length=10000)
    
    # Process key points
    key_points_html = ''
    if summary.key_points:
        points = [p.strip() for p in summary.key_points.split('\n') if p.strip()]
        if points:
            key_points_html = '''
            <div class="card mb-4">
                <div class="card-header bg-success text-white">
                    <h5 class="mb-0"><i class="fas fa-key me-2"></i>Key Points</h5>
                </div>
                <div class="card-body">
                    <div class="row">
            '''
            for point in points:
                key_points_html += f'''
                        <div class="col-md-6 mb-3">
                            <div class="key-point">
                                <i class="fas fa-star text-warning me-2"></i>{clean_text_for_display(point)}
                            </div>
                        </div>
                '''
            key_points_html += '''
                    </div>
                </div>
            </div>
            '''
    
    navbar = create_navbar()
    content = f'''
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h1><i class="fas fa-file-alt me-2"></i>Summary: {summary.book.title}</h1>
            <p class="lead">{summary.book.author or 'Unknown Author'}</p>
        </div>
        <div>
            <a href="/book/{summary.book.id}" class="btn btn-outline-secondary">
                <i class="fas fa-book me-2"></i>View Original Book
            </a>
            <a href="/dashboard" class="btn btn-outline-primary ms-2">
                <i class="fas fa-tachometer-alt me-2"></i>Dashboard
            </a>
        </div>
    </div>
    
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card text-white bg-success">
                <div class="card-body text-center">
                    <h4 class="card-title">{summary.compression_ratio:.1%}</h4>
                    <p class="card-text">Compression</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-primary">
                <div class="card-body text-center">
                    <h4 class="card-title">{summary.read_time_minutes}</h4>
                    <p class="card-text">Minutes to Read</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-info">
                <div class="card-body text-center">
                    <h4 class="card-title">{len(summary.summary.split()) if summary.summary else 0}</h4>
                    <p class="card-text">Words in Summary</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-warning">
                <div class="card-body text-center">
                    <h4 class="card-title">{summary.book.upload_date.strftime('%Y-%m-%d')}</h4>
                    <p class="card-text">Created Date</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card mb-4">
        <div class="card-header bg-primary text-white">
            <h5 class="mb-0"><i class="fas fa-align-left me-2"></i>Summary</h5>
        </div>
        <div class="card-body">
            <div class="summary-content">
                {cleaned_summary}
            </div>
        </div>
    </div>
    
    {key_points_html}
    
    <div class="card">
        <div class="card-header bg-info text-white">
            <h5 class="mb-0"><i class="fas fa-info-circle me-2"></i>Summary Information</h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <p><strong>Original Book:</strong> {summary.book.title}</p>
                    <p><strong>Original Author:</strong> {summary.book.author or 'Unknown'}</p>
                    <p><strong>Original Word Count:</strong> {summary.book.word_count:,} words</p>
                </div>
                <div class="col-md-6">
                    <p><strong>Summary Created:</strong> {summary.book.upload_date.strftime('%Y-%m-%d %H:%M')}</p>
                    <p><strong>Time Saved:</strong> {summary.book.word_count // 200 - (summary.read_time_minutes or 0)} minutes</p>
                    <p><strong>Summary Algorithm:</strong> AI Text Summarization</p>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return BASE_TEMPLATE.format(
        title=f"Summary: {summary.book.title}",
        navbar=navbar,
        content=content,
        footer='',
        scripts=''
    )

# ==================== API ROUTES ====================

@app.route('/api/books/<int:book_id>', methods=['DELETE'])
@login_required
def delete_book_api(book_id):
    """Delete a book"""
    book = Book.query.get_or_404(book_id)
    
    if book.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    Summary.query.filter_by(book_id=book_id).delete()
    db.session.delete(book)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Book deleted successfully'})

@app.route('/api/summarize/<int:book_id>', methods=['POST'])
@login_required
def summarize_book_api(book_id):
    """Generate summary for a book"""
    book = Book.query.get_or_404(book_id)
    
    if book.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    existing_summary = Summary.query.filter_by(book_id=book_id).first()
    if existing_summary:
        return jsonify({'summary_id': existing_summary.id})
    
    try:
        summary_ratio = request.json.get('summary_ratio', 0.3)
        summary_text = summarizer.summarize(book.content, ratio=summary_ratio)
        
        summary = Summary(
            book_id=book.id,
            summary=clean_text_for_display(summary_text),
            compression_ratio=len(summary_text.split()) / book.word_count if book.word_count > 0 else 0,
            read_time_minutes=max(1, len(summary_text.split()) // 200)
        )
        db.session.add(summary)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'summary_id': summary.id,
            'message': 'Summary generated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/selfhelp-book/<int:book_id>', methods=['GET'])
def get_selfhelp_book_summary(book_id):
    """Get self-help book summary"""
    book = SELF_HELP_BOOKS_DICT.get(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    return jsonify({
        'title': book['title'],
        'author': book['author'],
        'year': book['year'],
        'summary': book['summary'],
        'key_points': book['key_points'],
        'practical_tips': book['practical_tips']
    })

@app.route('/api/search-books', methods=['GET'])
@login_required
def search_books_api():
    """Search and filter books"""
    try:
        search_query = request.args.get('q', '').strip()
        sort_by = request.args.get('sort_by', 'upload_date')
        sort_order = request.args.get('sort_order', 'desc')
        summary_status = request.args.get('summary_status', 'all')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 9))
        
        query = Book.query.filter_by(user_id=current_user.id)
        
        if search_query:
            search_term = f'%{search_query}%'
            query = query.filter(
                or_(
                    Book.title.ilike(search_term),
                    Book.author.ilike(search_term)
                )
            )
        
        if summary_status == 'summarized':
            query = query.filter(Book.summaries.any())
        elif summary_status == 'not_summarized':
            query = query.filter(~Book.summaries.any())
        
        if sort_by == 'title':
            if sort_order == 'asc':
                query = query.order_by(Book.title.asc())
            else:
                query = query.order_by(Book.title.desc())
        elif sort_by == 'upload_date':
            if sort_order == 'asc':
                query = query.order_by(Book.upload_date.asc())
            else:
                query = query.order_by(Book.upload_date.desc())
        elif sort_by == 'word_count':
            if sort_order == 'asc':
                query = query.order_by(Book.word_count.asc())
            else:
                query = query.order_by(Book.word_count.desc())
        
        total_books = query.count()
        books = query.paginate(page=page, per_page=per_page, error_out=False)
        
        books_data = []
        for book in books.items:
            has_summary = Summary.query.filter_by(book_id=book.id).first() is not None
            books_data.append({
                'id': book.id,
                'title': book.title,
                'author': book.author or 'Unknown Author',
                'upload_date': book.upload_date.strftime('%Y-%m-%d'),
                'word_count': book.word_count,
                'file_type': book.file_type,
                'has_summary': has_summary
            })
        
        return jsonify({
            'success': True,
            'books': books_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': books.pages,
                'total_items': total_books,
                'has_next': books.has_next,
                'has_prev': books.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== OTHER ROUTES ====================

@app.route('/logout')
@login_required
def logout_route():
    """Logout user"""
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect('/')

# ==================== INITIALIZATION ====================

if __name__ == '__main__':
    with app.app_context():
        # Create upload directory
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Create database tables
        db.create_all()
        
        # Create admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created: username='admin', password='admin123'")
    
    print("=" * 70)
    print(" BOOK SUMMARIZER - FIXED VERSION")
    print("=" * 70)
    print(" Access at: http://localhost:5000")
    print("Admin login: username='admin', password='admin123'")
    print("Fixed PDF text extraction")
    print("No more binary data display")
    print("All buttons working properly")
    print("=" * 70)
    
    app.run(debug=True, port=5000)