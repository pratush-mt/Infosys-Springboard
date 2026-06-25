import os
import PyPDF2
import pdfplumber
from io import BytesIO

class FileProcessor:
    @staticmethod
    def extract_text_from_pdf(file_stream, use_pdfplumber=True):
        text = ""
        
        try:
            if use_pdfplumber:
                with pdfplumber.open(BytesIO(file_stream)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n\n"
            else:
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_stream))
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
        
        return text
    
    @staticmethod
    def extract_text_from_txt(file_stream):
        try:
            try:
                text = file_stream.read().decode('utf-8')
            except UnicodeDecodeError:
                file_stream.seek(0)
                text = file_stream.read().decode('latin-1')
            
            return text
        
        except Exception as e:
            raise Exception(f"Error reading text file: {str(e)}")
    
    @staticmethod
    def process_uploaded_file(file, file_type):
        file_stream = file.read()
        file.seek(0)
        
        if file_type == 'pdf':
            return FileProcessor.extract_text_from_pdf(file_stream)
        elif file_type == 'txt':
            return FileProcessor.extract_text_from_txt(BytesIO(file_stream))
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    @staticmethod
    def save_uploaded_file(file, upload_folder, filename):
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return file_path