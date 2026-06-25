from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    books = db.relationship('Book', backref='owner', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'

class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    original_text = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.String(10))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed_text = db.Column(db.Text)
    language = db.Column(db.String(10))
    word_count = db.Column(db.Integer)
    file_path = db.Column(db.String(500))
    
    summaries = db.relationship('Summary', backref='book', lazy=True, cascade='all, delete-orphan')

class Summary(db.Model):
    __tablename__ = 'summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    summary_length = db.Column(db.Integer)
    generation_date = db.Column(db.DateTime, default=datetime.utcnow)
    model_used = db.Column(db.String(50), default='extractive')
    reading_time = db.Column(db.Integer)
    key_points = db.Column(db.Text)