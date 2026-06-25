# utilities/ai_model.py
"""
AI Model Module for Task 9: AI Model Integration and API Development
Integrates DistilBART model with proper error handling, logging, and chunking strategies.
"""
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import logging
import time
import re
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIModelSummarizer:
    """
    Advanced AI summarizer using DistilBART with proper tokenization,
    truncation strategies, and error handling.
    """
    
    def __init__(self, model_name: str = "sshleifer/distilbart-cnn-12-6"):
        """
        Initialize the AI model summarizer.
        
        Args:
            model_name: Hugging Face model identifier
        """
        self.model_name = model_name
        self.device = -1  # CPU by default, change to 0 for GPU
        
        # Model configuration
        self.max_input_length = 1024
        self.max_summary_length = 150
        self.min_summary_length = 50
        self.chunk_size = 800  # Words per chunk
        
        # Initialize components
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        self.is_loaded = False
        
        # Performance tracking
        self.inference_times = []
        self.chunk_counts = []
        
        logger.info(f"Initialized AI Model Summarizer with model: {model_name}")
    
    def load_model(self) -> bool:
        """
        Load the AI model with error handling.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.is_loaded:
            logger.info("Model already loaded")
            return True
        
        try:
            start_time = time.time()
            logger.info(f"Loading model: {self.model_name}")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            
            # Create summarization pipeline
            self.pipeline = pipeline(
                "summarization",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device,
                truncation=True
            )
            
            load_time = time.time() - start_time
            self.is_loaded = True
            
            logger.info(f"Model loaded successfully in {load_time:.2f} seconds")
            logger.info(f"Device: {'GPU' if self.device == 0 else 'CPU'}")
            logger.info(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            self.is_loaded = False
            return False
    
    def _chunk_text_by_tokens(self, text: str, max_tokens: int = 800) -> List[str]:
        """
        Split text into chunks based on token count for optimal processing.
        
        Args:
            text: Input text to chunk
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List of text chunks
        """
        if not self.tokenizer:
            # Fallback to word-based chunking if tokenizer not loaded
            return self._chunk_text_by_words(text, max_tokens * 0.7)
        
        try:
            # Tokenize the entire text
            tokens = self.tokenizer.encode(text, truncation=False, add_special_tokens=False)
            
            if len(tokens) <= max_tokens:
                return [text]
            
            # Split by sentences first for better context preservation
            sentences = re.split(r'(?<=[.!?])\s+', text)
            chunks = []
            current_chunk = []
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = len(self.tokenizer.encode(sentence, add_special_tokens=False))
                
                if current_tokens + sentence_tokens > max_tokens and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
                else:
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
            
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            
            logger.info(f"Split text into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.warning(f"Token-based chunking failed: {e}. Using word-based fallback.")
            return self._chunk_text_by_words(text, int(max_tokens * 0.7))
    
    def _chunk_text_by_words(self, text: str, max_words: int = 560) -> List[str]:
        """
        Fallback chunking method based on word count.
        
        Args:
            text: Input text
            max_words: Maximum words per chunk
            
        Returns:
            List of text chunks
        """
        words = text.split()
        
        if len(words) <= max_words:
            return [text]
        
        chunks = []
        for i in range(0, len(words), max_words):
            chunk_words = words[i:i + max_words]
            chunks.append(' '.join(chunk_words))
        
        logger.info(f"Split text into {len(chunks)} word-based chunks")
        return chunks
    
    def _validate_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate input text before processing.
        
        Args:
            text: Input text to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Input text is empty"
        
        text = text.strip()
        word_count = len(text.split())
        
        if word_count < 50:
            return False, f"Text too short ({word_count} words). Minimum 50 words required."
        
        if word_count > 10000:
            logger.warning(f"Very long text detected: {word_count} words")
        
        return True, None
    
    def summarize_chunk(self, chunk: str, **kwargs) -> Dict:
        """
        Summarize a single text chunk with error handling.
        
        Args:
            chunk: Text chunk to summarize
            **kwargs: Additional summarization parameters
            
        Returns:
            Dictionary with summary and metadata
        """
        if not self.is_loaded and not self.load_model():
            return {
                'success': False,
                'error': 'Model failed to load',
                'summary': ''
            }
        
        try:
            # Default parameters
            params = {
                'max_length': kwargs.get('max_length', self.max_summary_length),
                'min_length': kwargs.get('min_length', self.min_summary_length),
                'length_penalty': kwargs.get('length_penalty', 2.0),
                'num_beams': kwargs.get('num_beams', 4),
                'early_stopping': kwargs.get('early_stopping', True),
                'no_repeat_ngram_size': kwargs.get('no_repeat_ngram_size', 3),
                'temperature': kwargs.get('temperature', 1.0),
                'do_sample': kwargs.get('do_sample', False)
            }
            
            start_time = time.time()
            
            # Generate summary
            result = self.pipeline(chunk, **params)
            summary_text = result[0]['summary_text']
            
            inference_time = time.time() - start_time
            self.inference_times.append(inference_time)
            
            # Calculate statistics
            original_words = len(chunk.split())
            summary_words = len(summary_text.split())
            compression_ratio = summary_words / original_words if original_words > 0 else 0
            
            return {
                'success': True,
                'summary': summary_text,
                'original_length': original_words,
                'summary_length': summary_words,
                'compression_ratio': round(compression_ratio, 3),
                'inference_time': round(inference_time, 2),
                'chunk_size': original_words
            }
            
        except torch.cuda.OutOfMemoryError:
            logger.error("CUDA out of memory error")
            return {
                'success': False,
                'error': 'CUDA out of memory',
                'summary': ''
            }
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.error("System out of memory error")
                return {
                    'success': False,
                    'error': 'System out of memory',
                    'summary': ''
                }
            else:
                logger.error(f"Runtime error: {str(e)}")
                return {
                    'success': False,
                    'error': f'Runtime error: {str(e)[:100]}',
                    'summary': ''
                }
        except Exception as e:
            logger.error(f"Unexpected error in summarization: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)[:100]}',
                'summary': ''
            }
    
    def summarize_text(self, text: str, compression_ratio: float = 0.3, **kwargs) -> Dict:
        """
        Summarize complete text with chunking strategy.
        
        Args:
            text: Complete text to summarize
            compression_ratio: Target compression ratio (0.1 to 0.5)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with summary and metadata
        """
        # Validate input
        is_valid, error_msg = self._validate_input(text)
        if not is_valid:
            return {
                'success': False,
                'error': error_msg,
                'summary': ''
            }
        
        # Load model if not loaded
        if not self.is_loaded and not self.load_model():
            return {
                'success': False,
                'error': 'Model failed to load',
                'summary': ''
            }
        
        try:
            start_time = time.time()
            
            # Calculate target summary length
            original_words = len(text.split())
            target_words = max(
                self.min_summary_length,
                min(self.max_summary_length, int(original_words * compression_ratio))
            )
            
            logger.info(f"Processing text: {original_words} words, target: {target_words} words")
            
            # Determine if chunking is needed
            if original_words > 1000:
                # Use token-based chunking for better context
                chunks = self._chunk_text_by_tokens(text, max_tokens=self.chunk_size)
                self.chunk_counts.append(len(chunks))
                
                if len(chunks) > 10:
                    logger.warning(f"Large number of chunks: {len(chunks)}. Processing may be slow.")
                
                # Summarize each chunk
                chunk_summaries = []
                successful_chunks = 0
                
                for i, chunk in enumerate(chunks, 1):
                    logger.info(f"Processing chunk {i}/{len(chunks)}")
                    
                    # Adjust parameters for chunk
                    chunk_params = kwargs.copy()
                    chunk_params['max_length'] = min(100, target_words // len(chunks) + 30)
                    chunk_params['min_length'] = 30
                    
                    chunk_result = self.summarize_chunk(chunk, **chunk_params)
                    
                    if chunk_result['success']:
                        chunk_summaries.append(chunk_result['summary'])
                        successful_chunks += 1
                    else:
                        logger.warning(f"Chunk {i} failed: {chunk_result.get('error', 'Unknown error')}")
                        # Continue with other chunks
                
                if successful_chunks == 0:
                    return {
                        'success': False,
                        'error': 'All chunks failed to summarize',
                        'summary': ''
                    }
                
                # Combine chunk summaries
                combined_summary = ' '.join(chunk_summaries)
                
                # If combined summary is still long, summarize it again
                if len(combined_summary.split()) > target_words * 1.5:
                    logger.info("Combined summary too long, performing final summarization")
                    final_params = kwargs.copy()
                    final_params['max_length'] = target_words
                    final_params['min_length'] = self.min_summary_length
                    
                    final_result = self.summarize_chunk(combined_summary, **final_params)
                    
                    if final_result['success']:
                        summary_text = final_result['summary']
                    else:
                        # Fallback to combined summary
                        summary_text = combined_summary[:target_words * 10]  # Limit length
                else:
                    summary_text = combined_summary
            else:
                # Direct summarization for shorter texts
                direct_params = kwargs.copy()
                direct_params['max_length'] = target_words
                direct_params['min_length'] = self.min_summary_length
                
                direct_result = self.summarize_chunk(text, **direct_params)
                
                if direct_result['success']:
                    summary_text = direct_result['summary']
                else:
                    return direct_result
            
            # Calculate final statistics
            total_time = time.time() - start_time
            summary_words = len(summary_text.split())
            final_compression = summary_words / original_words if original_words > 0 else 0
            read_time_minutes = max(1, summary_words // 200)
            
            # Extract key points (first few sentences)
            sentences = re.split(r'(?<=[.!?])\s+', summary_text)
            key_points = [s.strip() for s in sentences[:3] if len(s.split()) > 5]
            
            # Log performance
            avg_inference = sum(self.inference_times[-5:]) / min(5, len(self.inference_times)) if self.inference_times else 0
            logger.info(f"Summarization completed in {total_time:.2f}s "
                       f"(avg chunk: {avg_inference:.2f}s, "
                       f"compression: {final_compression:.1%})")
            
            return {
                'success': True,
                'summary': summary_text,
                'original_length': original_words,
                'summary_length': summary_words,
                'compression_ratio': round(final_compression, 3),
                'read_time_minutes': read_time_minutes,
                'processing_time': round(total_time, 2),
                'key_points': key_points,
                'model_used': self.model_name,
                'chunks_processed': len(self.chunk_counts) if original_words > 1000 else 1
            }
            
        except Exception as e:
            logger.error(f"Critical error in summarize_text: {str(e)}")
            return {
                'success': False,
                'error': f'Critical error: {str(e)[:100]}',
                'summary': ''
            }
    
    def get_performance_stats(self) -> Dict:
        """
        Get performance statistics for monitoring and optimization.
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.inference_times:
            return {
                'total_inferences': 0,
                'avg_inference_time': 0,
                'total_chunks': sum(self.chunk_counts) if self.chunk_counts else 0,
                'model_loaded': self.is_loaded
            }
        
        return {
            'total_inferences': len(self.inference_times),
            'avg_inference_time': round(sum(self.inference_times) / len(self.inference_times), 2),
            'min_inference_time': round(min(self.inference_times), 2) if self.inference_times else 0,
            'max_inference_time': round(max(self.inference_times), 2) if self.inference_times else 0,
            'total_chunks': sum(self.chunk_counts) if self.chunk_counts else 0,
            'avg_chunks_per_text': round(sum(self.chunk_counts) / len(self.chunk_counts), 1) if self.chunk_counts else 0,
            'model_loaded': self.is_loaded,
            'device': 'GPU' if self.device == 0 else 'CPU'
        }
    
    def cleanup(self):
        """Clean up model resources."""
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
        if self.pipeline:
            del self.pipeline
        
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        self.is_loaded = False
        logger.info("Model resources cleaned up")


# Global instance for easy access
_ai_summarizer_instance = None

def get_ai_summarizer(model_name: str = "sshleifer/distilbart-cnn-12-6") -> AIModelSummarizer:
    """
    Factory function to get or create AI summarizer instance.
    
    Args:
        model_name: Model identifier
        
    Returns:
        AIModelSummarizer instance
    """
    global _ai_summarizer_instance
    
    if _ai_summarizer_instance is None:
        _ai_summarizer_instance = AIModelSummarizer(model_name)
    
    return _ai_summarizer_instance


# Test function for module verification
def test_ai_module():
    """Test function to verify the AI module works correctly."""
    print("=" * 60)
    print("Testing AI Model Module")
    print("=" * 60)
    
    try:
        # Create summarizer
        summarizer = AIModelSummarizer("sshleifer/distilbart-cnn-6-6")  # Smaller model for testing
        
        # Test loading
        print("1. Testing model loading...")
        if summarizer.load_model():
            print("   ✅ Model loaded successfully")
        else:
            print("   ❌ Model loading failed")
            return False
        
        # Test summarization
        print("\n2. Testing summarization...")
        test_text = """
        Artificial Intelligence is transforming how we interact with technology. 
        Machine learning algorithms can now understand natural language, recognize images, 
        and make predictions with remarkable accuracy. These advancements are creating 
        new opportunities in healthcare, education, and business automation.
        """
        
        result = summarizer.summarize_text(test_text, compression_ratio=0.3)
        
        if result['success']:
            print(f"   ✅ Summarization successful")
            print(f"   Original: {result['original_length']} words")
            print(f"   Summary: {result['summary_length']} words")
            print(f"   Compression: {result['compression_ratio']:.1%}")
            print(f"   Summary: {result['summary'][:100]}...")
        else:
            print(f"   ❌ Summarization failed: {result.get('error', 'Unknown error')}")
            return False
        
        # Test performance stats
        print("\n3. Testing performance tracking...")
        stats = summarizer.get_performance_stats()
        print(f"   ✅ Performance stats collected")
        print(f"   Total inferences: {stats['total_inferences']}")
        print(f"   Average time: {stats['avg_inference_time']}s")
        
        # Cleanup
        summarizer.cleanup()
        
        print("\n" + "=" * 60)
        print("✅ AI Model Module Test PASSED")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ AI Module Test FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    # Run test if module is executed directly
    test_ai_module()
    
    