import re
from langdetect import detect, LangDetectException

class TextPreprocessor:
    @staticmethod
    def clean_text(text, remove_citations=True, remove_footnotes=True, remove_page_numbers=True):
        if not text:
            return ""
        
        text = ' '.join(text.split())
        
        if remove_citations:
            text = re.sub(r'\[\d+\]', '', text)
            text = re.sub(r'\(\d{4}\)', '', text)
        
        if remove_footnotes:
            text = re.sub(r'footnote\s*:\s*.*?(?=\n\n|\Z)', '', text, flags=re.IGNORECASE)
            text = re.sub(r'fn\.?\s*\d+.*?(?=\n\n|\Z)', '', text, flags=re.IGNORECASE)
        
        if remove_page_numbers:
            text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
            text = re.sub(r'\s+\d+\s*$', '', text, flags=re.MULTILINE)
        
        text = re.sub(r'[^\w\s.,!?;:\-\'"()]', '', text)
        text = text.replace('"', '"').replace("'", "'")
        text = text.replace('–', '-').replace('—', '-')
        
        return text.strip()
    
    @staticmethod
    def detect_language(text):
        try:
            return detect(text[:1000])
        except LangDetectException:
            return 'en'
    
    @staticmethod
    def split_into_chunks(text, chunk_size=1500, overlap=100):
        words = text.split()
        chunks = []
        
        if len(words) <= chunk_size:
            return [text]
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            
            if i + chunk_size >= len(words):
                break
        
        return chunks
    
    @staticmethod
    def calculate_word_count(text):
        return len(text.split())
    
    @staticmethod
    def estimate_reading_time(word_count, words_per_minute=200):
        return max(1, round(word_count / words_per_minute))