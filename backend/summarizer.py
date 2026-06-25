from models.models import db, Book, Summary
from utilities.preprocessor import TextPreprocessor
from datetime import datetime

class Summarizer:
    def __init__(self):
        self.preprocessor = TextPreprocessor()
    
    def generate_extractive_summary(self, text, summary_ratio=0.3):
        sentences = text.split('. ')
        if len(sentences) <= 1:
            return text
        
        num_sentences = max(3, int(len(sentences) * summary_ratio))
        
        important_indices = []
        if num_sentences >= 3:
            important_indices = [0]
            if len(sentences) > 1:
                important_indices.append(len(sentences) // 2)
            important_indices.append(-1)
        
        while len(important_indices) < num_sentences and len(important_indices) < len(sentences):
            for i in range(1, len(sentences) - 1):
                if i not in important_indices and i not in [0, len(sentences)//2, len(sentences)-1]:
                    important_indices.append(i)
                    if len(important_indices) >= num_sentences:
                        break
        
        important_indices.sort()
        summary_sentences = [sentences[i] if i < len(sentences) else sentences[-1] 
                            for i in important_indices]
        
        summary = '. '.join(summary_sentences)
        if not summary.endswith('.'):
            summary += '.'
        
        return summary
    
    def generate_key_points(self, text, num_points=5):
        sentences = text.split('. ')
        if len(sentences) <= num_points:
            return sentences
        
        paragraphs = text.split('\n\n')
        key_points = []
        
        for para in paragraphs[:num_points]:
            first_sentence = para.split('. ')[0]
            if first_sentence and len(first_sentence.split()) > 5:
                key_points.append(first_sentence.strip() + '.')
        
        return key_points[:num_points]
    
    def create_summary(self, book_id, summary_ratio=0.3):
        book = Book.query.get_or_404(book_id)
        
        cleaned_text = self.preprocessor.clean_text(book.processed_text or book.original_text)
        summary_text = self.generate_extractive_summary(cleaned_text, summary_ratio)
        key_points = self.generate_key_points(cleaned_text)
        
        summary_length = self.preprocessor.calculate_word_count(summary_text)
        reading_time = self.preprocessor.estimate_reading_time(summary_length)
        
        summary = Summary(
            book_id=book_id,
            summary_text=summary_text,
            summary_length=summary_length,
            model_used='extractive',
            reading_time=reading_time,
            key_points='\n'.join(key_points)
        )
        
        db.session.add(summary)
        db.session.commit()
        
        return summary