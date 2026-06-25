# utilities/text_chunker.py
import re
import logging
from typing import List, Dict, Tuple, Optional
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

logger = logging.getLogger(__name__)

class TextChunker:
    """Intelligent text chunking system for processing large books"""
    
    def __init__(self, max_tokens: int = 1024, overlap_tokens: int = 100):
        """
        Initialize text chunker
        
        Args:
            max_tokens: Maximum tokens per chunk (default: 1024)
            overlap_tokens: Token overlap between chunks (default: 100)
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        
        # Try to download NLTK data if not available
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            try:
                nltk.download('punkt')
                nltk.download('punkt_tab')
            except:
                logger.warning("NLTK punkt not available, using simple sentence splitting")
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (simplified - 1 token ≈ 4 characters for English text)"""
        # Simple estimation: tokens ≈ words * 1.3 (accounts for punctuation)
        words = len(text.split())
        return int(words * 1.3)
    
    def find_natural_breakpoints(self, text: str) -> List[int]:
        """Find natural breakpoints in text (paragraphs, chapters, sentences)"""
        breakpoints = []
        
        # Find chapter breaks (common patterns)
        chapter_patterns = [
            r'\nCHAPTER\s+\w+\n',
            r'\nChapter\s+\w+\n',
            r'\n\d+\.\s+',  # Numbered chapters like "1. "
            r'\n[IVXLCDM]+\.\s+',  # Roman numerals
            r'\n\*\*\*\s*\n',  # Scene breaks
        ]
        
        for pattern in chapter_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if match.start() not in breakpoints:
                    breakpoints.append(match.start())
        
        # Find paragraph breaks (double newlines)
        for match in re.finditer(r'\n\s*\n', text):
            if match.start() not in breakpoints:
                breakpoints.append(match.start())
        
        # Sort breakpoints
        breakpoints.sort()
        return breakpoints
    
    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using NLTK or fallback"""
        try:
            sentences = sent_tokenize(text)
        except:
            # Fallback: split on sentence endings
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def create_chunks_with_overlap(self, text: str, book_id: int) -> List[Dict]:
        """
        Create overlapping chunks from text with intelligent breaking
        
        Args:
            text: Text to chunk
            book_id: ID of the book for tracking
        
        Returns:
            List of chunk dictionaries with metadata
        """
        if not text or not text.strip():
            return []
        
        logger.info(f"Creating chunks for book {book_id}, text length: {len(text)} chars")
        
        # Get natural breakpoints
        breakpoints = self.find_natural_breakpoints(text)
        logger.info(f"Found {len(breakpoints)} natural breakpoints")
        
        # Estimate total tokens
        total_tokens = self.estimate_tokens(text)
        logger.info(f"Estimated total tokens: {total_tokens}")
        
        # If text is small enough, return as single chunk
        if total_tokens <= self.max_tokens:
            return [{
                'book_id': book_id,
                'chunk_number': 1,
                'content': text.strip(),
                'start_pos': 0,
                'end_pos': len(text),
                'tokens_estimated': total_tokens,
                'total_chunks': 1
            }]
        
        chunks = []
        current_pos = 0
        chunk_number = 1
        
        # First, try to split at natural breakpoints
        while current_pos < len(text):
            # Calculate target end position
            target_end = current_pos + (self.max_tokens * 4)  # Approximate character count
            
            # Don't exceed text length
            if target_end > len(text):
                target_end = len(text)
            
            # Find the best breakpoint near target_end
            best_breakpoint = target_end
            
            # Look for breakpoints in a window around target_end
            window_start = max(current_pos, target_end - 200)
            window_end = min(len(text), target_end + 200)
            
            for bp in breakpoints:
                if window_start <= bp <= window_end:
                    # Prefer breakpoints that are not too far from target
                    if abs(bp - target_end) < abs(best_breakpoint - target_end):
                        best_breakpoint = bp
            
            # If we're near the end, adjust
            if best_breakpoint == current_pos and current_pos > 0:
                # Move forward a bit to avoid infinite loop
                best_breakpoint = min(current_pos + 100, len(text))
            
            # Extract chunk content
            chunk_content = text[current_pos:best_breakpoint].strip()
            
            if chunk_content:  # Only add non-empty chunks
                chunk_tokens = self.estimate_tokens(chunk_content)
                
                chunks.append({
                    'book_id': book_id,
                    'chunk_number': chunk_number,
                    'content': chunk_content,
                    'start_pos': current_pos,
                    'end_pos': best_breakpoint,
                    'tokens_estimated': chunk_tokens,
                    'total_chunks': None  # Will be set later
                })
                chunk_number += 1
            
            # Move position for next chunk with overlap
            if best_breakpoint < len(text):
                # Move back for overlap
                overlap_start = max(current_pos, best_breakpoint - (self.overlap_tokens * 4))
                current_pos = overlap_start
            else:
                current_pos = best_breakpoint
        
        # Update total chunks count
        for chunk in chunks:
            chunk['total_chunks'] = len(chunks)
        
        logger.info(f"Created {len(chunks)} chunks for book {book_id}")
        return chunks
    
    def merge_summaries(self, chunk_summaries: List[Dict]) -> str:
        """
        Merge summaries from multiple chunks into a coherent final summary
        
        Args:
            chunk_summaries: List of chunk summary dictionaries with 'chunk_number' and 'summary'
        
        Returns:
            Merged and deduplicated summary
        """
        if not chunk_summaries:
            return ""
        
        # Sort by chunk number
        sorted_summaries = sorted(chunk_summaries, key=lambda x: x['chunk_number'])
        
        # Extract just the summary texts
        summaries = [s['summary'] for s in sorted_summaries]
        
        # Simple merging strategy
        if len(summaries) == 1:
            return summaries[0]
        
        # For multiple chunks, combine and deduplicate
        merged = " ".join(summaries)
        
        # Remove duplicate sentences
        sentences = self.split_into_sentences(merged)
        
        # Simple deduplication (case-insensitive)
        unique_sentences = []
        seen_sentences = set()
        
        for sentence in sentences:
            # Normalize sentence for comparison
            normalized = sentence.lower().strip()
            if normalized not in seen_sentences and len(normalized) > 10:
                seen_sentences.add(normalized)
                unique_sentences.append(sentence)
        
        # Reconstruct summary
        final_summary = " ".join(unique_sentences)
        
        # Ensure coherence
        final_summary = self.ensure_coherence(final_summary)
        
        return final_summary
    
    def ensure_coherence(self, summary: str) -> str:
        """Ensure summary coherence by fixing common issues"""
        if not summary:
            return ""
        
        # Remove excessive repetition
        sentences = self.split_into_sentences(summary)
        
        if len(sentences) <= 1:
            return summary
        
        # Ensure proper spacing
        summary = re.sub(r'\s+', ' ', summary)
        summary = re.sub(r'\s+([.,!?])', r'\1', summary)
        
        # Capitalize first letter
        if summary and summary[0].islower():
            summary = summary[0].upper() + summary[1:]
        
        return summary.strip()
    
    def get_chunking_stats(self, text: str) -> Dict:
        """Get statistics about chunking for a given text"""
        total_chars = len(text)
        total_tokens = self.estimate_tokens(text)
        breakpoints = self.find_natural_breakpoints(text)
        
        # Estimate chunk count
        if total_tokens <= self.max_tokens:
            estimated_chunks = 1
        else:
            estimated_chunks = max(2, (total_tokens // (self.max_tokens - self.overlap_tokens)) + 1)
        
        return {
            'total_chars': total_chars,
            'total_tokens_estimated': total_tokens,
            'natural_breakpoints': len(breakpoints),
            'estimated_chunks': estimated_chunks,
            'chunk_size_tokens': self.max_tokens,
            'overlap_tokens': self.overlap_tokens
        }


# Singleton instance
_text_chunker = None

def get_text_chunker(max_tokens: int = 1024, overlap_tokens: int = 100) -> TextChunker:
    """Get or create text chunker instance"""
    global _text_chunker
    if _text_chunker is None:
        _text_chunker = TextChunker(max_tokens, overlap_tokens)
    return _text_chunker