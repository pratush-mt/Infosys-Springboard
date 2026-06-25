import os
from werkzeug.utils import secure_filename

class FileValidator:
    def __init__(self, allowed_extensions=None, max_size_mb=10):
        self.allowed_extensions = allowed_extensions or {'txt', 'pdf'}
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    def validate_file(self, file):
        if not file or file.filename == '':
            return False, 'No file selected'
        
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if file_extension not in self.allowed_extensions:
            return False, f'File type not allowed. Allowed: {", ".join(self.allowed_extensions)}'
        
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > self.max_size_bytes:
            return False, f'File too large. Maximum size is {self.max_size_bytes // (1024*1024)}MB'
        
        return True, filename
    
    def validate_text_input(self, text, max_chars=100000):
        if not text or not text.strip():
            return False, 'Text cannot be empty'
        
        if len(text) > max_chars:
            return False, f'Text too long. Maximum {max_chars} characters allowed'
        
        return True, text.strip()