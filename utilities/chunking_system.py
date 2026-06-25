"""
Chunking System Module for Task 10: Chunking Strategy and Context Preservation
Implements intelligent text chunking with overlapping boundaries for processing long books.
"""
import re
import logging
import math
from typing import List, Dict, Tuple, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    content: str
    index: int
    word_count: int
    start_position: int
    end_position: int
    has_overlap: bool = False
    overlap_size: int = 0

class ChunkingStrategy(ABC):
    """Abstract base class for chunking strategies"""
    
    @abstractmethod
    def create_chunks(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        """
        Split text into chunks based on the strategy
        
        Args:
            text: Input text to chunk
            max_chunk_size: Maximum words per chunk
            overlap: Overlap size in words between chunks
            
        Returns:
            List of chunk dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of the chunking strategy"""
        pass

class ParagraphBasedChunking(ChunkingStrategy):
    """Chunk text based on paragraph boundaries"""
    
    def create_chunks(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for i, paragraph in enumerate(paragraphs):
            para_words = paragraph.split()
            para_word_count = len(para_words)
            
            if current_word_count + para_word_count > max_chunk_size and current_chunk:
                # Create chunk from current paragraphs
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(self._create_chunk_dict(
                    chunk_text, len(chunks), current_word_count, 0, 0
                ))
                
                # Start new chunk with current paragraph
                current_chunk = [paragraph]
                current_word_count = para_word_count
            else:
                current_chunk.append(paragraph)
                current_word_count += para_word_count
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(self._create_chunk_dict(
                chunk_text, len(chunks), current_word_count, 0, 0
            ))
        
        # Add overlap between chunks
        self._add_overlap(chunks, overlap)
        
        return chunks
    
    def _add_overlap(self, chunks: List[Dict], overlap: int):
        """Add overlap between consecutive chunks"""
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            curr_chunk = chunks[i]
            
            if overlap > 0:
                # Get words from end of previous chunk
                prev_words = prev_chunk['content'].split()
                overlap_words = prev_words[-overlap:] if len(prev_words) > overlap else prev_words
                
                if overlap_words:
                    # Add overlap to current chunk
                    curr_words = curr_chunk['content'].split()
                    curr_chunk['content'] = ' '.join(overlap_words + curr_words)
                    curr_chunk['has_overlap'] = True
                    curr_chunk['overlap_size'] = len(overlap_words)
    
    def _create_chunk_dict(self, content: str, index: int, word_count: int, 
                          start_pos: int, end_pos: int) -> Dict:
        return {
            'content': content,
            'index': index,
            'word_count': word_count,
            'start_position': start_pos,
            'end_position': end_pos,
            'has_overlap': False,
            'overlap_size': 0
        }
    
    def get_strategy_name(self) -> str:
        return "paragraph"

class SentenceBasedChunking(ChunkingStrategy):
    """Chunk text based on sentence boundaries"""
    
    def create_chunks(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        # Split text into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)
            
            if current_word_count + sentence_word_count > max_chunk_size and current_chunk:
                # Create chunk from current sentences
                chunk_text = ' '.join(current_chunk)
                chunks.append(self._create_chunk_dict(
                    chunk_text, len(chunks), current_word_count, 0, 0
                ))
                
                # Start new chunk with current sentence
                current_chunk = [sentence]
                current_word_count = sentence_word_count
            else:
                current_chunk.append(sentence)
                current_word_count += sentence_word_count
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(self._create_chunk_dict(
                chunk_text, len(chunks), current_word_count, 0, 0
            ))
        
        # Add overlap between chunks
        self._add_overlap(chunks, overlap)
        
        return chunks
    
    def _add_overlap(self, chunks: List[Dict], overlap: int):
        """Add overlap between consecutive chunks"""
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            curr_chunk = chunks[i]
            
            if overlap > 0:
                # Get sentences from end of previous chunk
                prev_sentences = re.split(r'(?<=[.!?])\s+', prev_chunk['content'])
                overlap_sentences = []
                overlap_word_count = 0
                
                # Add sentences until we reach overlap size
                for sentence in reversed(prev_sentences):
                    sentence_words = sentence.split()
                    if overlap_word_count + len(sentence_words) <= overlap:
                        overlap_sentences.insert(0, sentence)
                        overlap_word_count += len(sentence_words)
                    else:
                        break
                
                if overlap_sentences:
                    # Add overlap to current chunk
                    curr_chunk['content'] = ' '.join(overlap_sentences) + ' ' + curr_chunk['content']
                    curr_chunk['has_overlap'] = True
                    curr_chunk['overlap_size'] = overlap_word_count
    
    def _create_chunk_dict(self, content: str, index: int, word_count: int, 
                          start_pos: int, end_pos: int) -> Dict:
        return {
            'content': content,
            'index': index,
            'word_count': word_count,
            'start_position': start_pos,
            'end_position': end_pos,
            'has_overlap': False,
            'overlap_size': 0
        }
    
    def get_strategy_name(self) -> str:
        return "sentence"

class FixedSizeChunking(ChunkingStrategy):
    """Chunk text into fixed-size chunks"""
    
    def create_chunks(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        words = text.split()
        chunks = []
        total_words = len(words)
        
        start_idx = 0
        chunk_index = 0
        
        while start_idx < total_words:
            # Calculate end index with overlap consideration
            end_idx = min(start_idx + max_chunk_size, total_words)
            
            # Get chunk words
            chunk_words = words[start_idx:end_idx]
            
            # Create chunk
            chunk_text = ' '.join(chunk_words)
            chunks.append(self._create_chunk_dict(
                chunk_text, chunk_index, len(chunk_words), start_idx, end_idx
            ))
            
            # Move start index for next chunk (with overlap)
            start_idx = end_idx - overlap if overlap > 0 else end_idx
            chunk_index += 1
        
        # Mark chunks that have overlap
        for i in range(1, len(chunks)):
            if chunks[i]['start_position'] < chunks[i-1]['end_position']:
                chunks[i]['has_overlap'] = True
                chunks[i]['overlap_size'] = chunks[i-1]['end_position'] - chunks[i]['start_position']
        
        return chunks
    
    def _create_chunk_dict(self, content: str, index: int, word_count: int, 
                          start_pos: int, end_pos: int) -> Dict:
        return {
            'content': content,
            'index': index,
            'word_count': word_count,
            'start_position': start_pos,
            'end_position': end_pos,
            'has_overlap': False,
            'overlap_size': 0
        }
    
    def get_strategy_name(self) -> str:
        return "fixed"

class SmartAdaptiveChunking(ChunkingStrategy):
    """Smart adaptive chunking that considers text structure"""
    
    def create_chunks(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        # First, try to split by major sections (chapters)
        chapters = self._split_by_chapters(text)
        
        if len(chapters) > 1:
            logger.info(f"Found {len(chapters)} chapters/sections")
            chunks = []
            
            for chapter_idx, chapter in enumerate(chapters):
                # Process each chapter with paragraph-based chunking
                chapter_chunker = ParagraphBasedChunking()
                chapter_chunks = chapter_chunker.create_chunks(
                    chapter, max_chunk_size, overlap
                )
                
                # Adjust indices for global positioning
                for chunk in chapter_chunks:
                    chunk['index'] = len(chunks)
                    chunk['chapter'] = chapter_idx
                    chunks.append(chunk)
            
            return chunks
        
        # If no chapters found, use paragraph-based with smart adjustments
        return self._smart_paragraph_chunking(text, max_chunk_size, overlap)
    
    def _split_by_chapters(self, text: str) -> List[str]:
        """Split text by chapter/section markers"""
        chapter_patterns = [
            r'\n(?:CHAPTER|Chapter|Chapter\s+\d+)[\s:]+.*?\n',
            r'\n\d+\.\s+[A-Z].*?\n',  # Numbered sections like "1. Introduction"
            r'\n[A-Z][A-Z\s]+\n',  # ALL CAPS headings
            r'\n={3,}\s*\n',  # Horizontal rule with text before/after
        ]
        
        for pattern in chapter_patterns:
            matches = list(re.finditer(pattern, text, re.DOTALL))
            if len(matches) > 1:  # Found multiple chapters
                chapters = []
                last_end = 0
                
                for match in matches:
                    if match.start() > last_end:
                        chapters.append(text[last_end:match.start()])
                    last_end = match.end()
                
                # Add final chapter
                if last_end < len(text):
                    chapters.append(text[last_end:])
                
                # Filter out empty chapters
                chapters = [ch for ch in chapters if ch.strip()]
                
                if len(chapters) > 1:
                    return chapters
        
        # If no chapters found, return whole text as single chapter
        return [text]
    
    def _smart_paragraph_chunking(self, text: str, max_chunk_size: int, overlap: int) -> List[Dict]:
        """Smart paragraph-based chunking with adaptive sizing"""
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for i, paragraph in enumerate(paragraphs):
            para_words = paragraph.split()
            para_word_count = len(para_words)
            
            # Calculate adaptive chunk size based on paragraph structure
            adaptive_size = self._calculate_adaptive_size(
                para_word_count, max_chunk_size, current_word_count
            )
            
            if current_word_count + para_word_count > adaptive_size and current_chunk:
                # Create chunk from current paragraphs
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(self._create_chunk_dict(
                    chunk_text, len(chunks), current_word_count, 0, 0
                ))
                
                # Start new chunk with current paragraph
                current_chunk = [paragraph]
                current_word_count = para_word_count
            else:
                current_chunk.append(paragraph)
                current_word_count += para_word_count
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(self._create_chunk_dict(
                chunk_text, len(chunks), current_word_count, 0, 0
            ))
        
        # Add smart overlap
        self._add_smart_overlap(chunks, overlap)
        
        return chunks
    
    def _calculate_adaptive_size(self, para_size: int, max_size: int, current_size: int) -> int:
        """Calculate adaptive chunk size based on context"""
        # Adjust chunk size based on paragraph size
        if para_size > max_size * 0.7:  # Large paragraph
            return max_size  # Allow larger chunks
        elif para_size < 50:  # Small paragraph
            return int(max_size * 0.8)  # Smaller chunks for better context
        else:
            return max_size
    
    def _add_smart_overlap(self, chunks: List[Dict], overlap: int):
        """Add smart overlap that preserves context"""
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            curr_chunk = chunks[i]
            
            if overlap > 0:
                # Get last paragraph from previous chunk
                prev_paragraphs = prev_chunk['content'].split('\n\n')
                if prev_paragraphs:
                    last_para = prev_paragraphs[-1]
                    last_para_words = last_para.split()
                    
                    # Use entire last paragraph if it's not too large
                    if len(last_para_words) <= overlap * 1.5:
                        overlap_text = last_para
                        overlap_size = len(last_para_words)
                    else:
                        # Use portion of last paragraph
                        overlap_words = last_para_words[-overlap:]
                        overlap_text = ' '.join(overlap_words)
                        overlap_size = overlap
                    
                    # Add overlap to current chunk
                    curr_chunk['content'] = overlap_text + '\n\n' + curr_chunk['content']
                    curr_chunk['has_overlap'] = True
                    curr_chunk['overlap_size'] = overlap_size
    
    def _create_chunk_dict(self, content: str, index: int, word_count: int, 
                          start_pos: int, end_pos: int) -> Dict:
        return {
            'content': content,
            'index': index,
            'word_count': word_count,
            'start_position': start_pos,
            'end_position': end_pos,
            'has_overlap': False,
            'overlap_size': 0
        }
    
    def get_strategy_name(self) -> str:
        return "smart"

class TextChunker:
    """Main text chunker class that uses strategies"""
    
    def __init__(self, max_chunk_size: int = 800, overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.strategies = {
            'paragraph': ParagraphBasedChunking(),
            'sentence': SentenceBasedChunking(),
            'fixed': FixedSizeChunking(),
            'smart': SmartAdaptiveChunking()
        }
    
    def chunk_text(self, text: str, strategy: str = "smart") -> List[Dict]:
        """Chunk text using specified strategy"""
        if strategy not in self.strategies:
            logger.warning(f"Strategy '{strategy}' not found. Using 'smart' instead.")
            strategy = "smart"
        
        chunker = self.strategies[strategy]
        chunks = chunker.create_chunks(text, self.max_chunk_size, self.overlap)
        
        logger.info(f"Created {len(chunks)} chunks using {strategy} strategy")
        
        # Calculate statistics
        if chunks:
            total_words = sum(chunk['word_count'] for chunk in chunks)
            avg_size = total_words // len(chunks)
            chunks_with_overlap = sum(1 for chunk in chunks if chunk['has_overlap'])
            
            logger.info(f"Chunk statistics: {total_words} total words, "
                       f"{avg_size} avg chunk size, "
                       f"{chunks_with_overlap} chunks with overlap")
        
        return chunks
    
    def get_chunk_info(self, text: str, strategy: str = "smart") -> Dict:
        """Get information about chunking without actually chunking"""
        chunks = self.chunk_text(text, strategy)
        
        return {
            'strategy': strategy,
            'total_chunks': len(chunks),
            'average_chunk_size': sum(c['word_count'] for c in chunks) // len(chunks) if chunks else 0,
            'chunks_with_overlap': sum(1 for c in chunks if c['has_overlap']),
            'recommended_strategy': self._recommend_strategy(text)
        }
    
    def _recommend_strategy(self, text: str) -> str:
        """Recommend best chunking strategy based on text characteristics"""
        # Analyze text structure
        paragraphs = re.split(r'\n\s*\n', text.strip())
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        words = text.split()
        
        # Calculate metrics
        avg_para_length = len(words) // max(1, len(paragraphs))
        avg_sentence_length = len(words) // max(1, len(sentences))
        
        # Make recommendation
        if len(paragraphs) > 10 and avg_para_length < 200:
            return "paragraph"
        elif avg_sentence_length > 25 and len(sentences) > 20:
            return "sentence"
        elif len(words) > 5000:
            return "smart"
        else:
            return "fixed"

class ChunkManager:
    """Manages chunks and their metadata"""
    
    def __init__(self):
        self.chunks_by_book = {}
        self.chunk_metadata = {}
    
    def store_chunks(self, book_id: int, chunks: List[Dict]):
        """Store chunks for a book"""
        self.chunks_by_book[book_id] = chunks
        
        # Store metadata
        self.chunk_metadata[book_id] = {
            'total_chunks': len(chunks),
            'chunk_sizes': [chunk['word_count'] for chunk in chunks],
            'chunks_with_overlap': sum(1 for chunk in chunks if chunk['has_overlap']),
            'total_words': sum(chunk['word_count'] for chunk in chunks)
        }
        
        logger.info(f"Stored {len(chunks)} chunks for book {book_id}")
        return len(chunks)
    
    def get_chunks(self, book_id: int) -> List[Dict]:
        """Get chunks for a book"""
        return self.chunks_by_book.get(book_id, [])
    
    def get_chunk_metadata(self, book_id: int) -> Dict:
        """Get metadata for book chunks"""
        return self.chunk_metadata.get(book_id, {})
    
    def clear_chunks(self, book_id: int):
        """Clear chunks for a book"""
        if book_id in self.chunks_by_book:
            del self.chunks_by_book[book_id]
            del self.chunk_metadata[book_id]
            logger.info(f"Cleared chunks for book {book_id}")
    
    def get_all_books(self) -> List[int]:
        """Get list of all books with stored chunks"""
        return list(self.chunks_by_book.keys())

class SmartTextProcessor:
    """Advanced text processing for chunking"""
    
    def __init__(self):
        self.sentence_endings = r'[.!?]+'
        self.paragraph_separators = r'\n\s*\n'
        self.heading_patterns = [
            r'^(?:CHAPTER|Chapter|Section|Part)\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[A-Z][A-Z\s]+$'
        ]
    
    def analyze_text_structure(self, text: str) -> Dict:
        """Analyze text structure for intelligent chunking"""
        # Basic statistics
        words = text.split()
        sentences = re.split(self.sentence_endings, text)
        paragraphs = re.split(self.paragraph_separators, text.strip())
        
        # Filter empty strings
        sentences = [s.strip() for s in sentences if s.strip()]
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Calculate metrics
        avg_sentence_length = len(words) // max(1, len(sentences))
        avg_paragraph_length = len(words) // max(1, len(paragraphs))
        
        # Detect headings
        headings = []
        for para in paragraphs[:20]:  # Check first 20 paragraphs
            for pattern in self.heading_patterns:
                if re.match(pattern, para, re.MULTILINE):
                    headings.append(para[:100])  # Store first 100 chars
                    break
        
        # Estimate reading time (200 words per minute)
        reading_time_minutes = max(1, len(words) // 200)
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'paragraph_count': len(paragraphs),
            'avg_sentence_length': avg_sentence_length,
            'avg_paragraph_length': avg_paragraph_length,
            'heading_count': len(headings),
            'headings': headings[:5],  # First 5 headings
            'reading_time_minutes': reading_time_minutes,
            'needs_chunking': len(words) > 1500  # Rough threshold
        }
    
    def find_natural_breaks(self, text: str) -> List[int]:
        """Find natural break points in text"""
        breaks = []
        
        # Find paragraph breaks
        for match in re.finditer(self.paragraph_separators, text):
            breaks.append(match.start())
        
        # Find potential chapter/section breaks
        heading_pattern = r'\n(?:CHAPTER|Chapter|\d+\.\s+[A-Z]|[A-Z][A-Z\s]+)\n'
        for match in re.finditer(heading_pattern, text):
            breaks.append(match.start())
        
        # Sort and return unique breaks
        return sorted(set(breaks))
    
    def split_at_breaks(self, text: str, max_chunk_size: int) -> List[Dict]:
        """Split text at natural breaks, respecting max chunk size"""
        breaks = self.find_natural_breaks(text)
        chunks = []
        start_pos = 0
        
        for break_pos in breaks:
            # Calculate chunk from start_pos to break_pos
            chunk_text = text[start_pos:break_pos]
            word_count = len(chunk_text.split())
            
            if word_count > max_chunk_size * 0.7:  # If chunk is reasonably large
                chunks.append({
                    'content': chunk_text,
                    'word_count': word_count,
                    'start_position': start_pos,
                    'end_position': break_pos
                })
                start_pos = break_pos
        
        # Add final chunk
        if start_pos < len(text):
            chunk_text = text[start_pos:]
            word_count = len(chunk_text.split())
            chunks.append({
                'content': chunk_text,
                'word_count': word_count,
                'start_position': start_pos,
                'end_position': len(text)
            })
        
        return chunks
    
    def optimize_chunk_sizes(self, chunks: List[Dict], target_size: int) -> List[Dict]:
        """Optimize chunk sizes by merging small chunks"""
        if not chunks:
            return chunks
        
        optimized = []
        current_chunk = chunks[0].copy()
        
        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            
            # Check if merging would exceed target size
            merged_size = current_chunk['word_count'] + next_chunk['word_count']
            
            if merged_size <= target_size * 1.2:  # Allow 20% overflow
                # Merge chunks
                current_chunk['content'] += '\n\n' + next_chunk['content']
                current_chunk['word_count'] = merged_size
                current_chunk['end_position'] = next_chunk['end_position']
            else:
                # Add current chunk and start new one
                optimized.append(current_chunk)
                current_chunk = next_chunk.copy()
        
        # Add final chunk
        optimized.append(current_chunk)
        
        logger.info(f"Optimized {len(chunks)} chunks to {len(optimized)} chunks")
        return optimized

# Factory function for getting chunking strategies
def get_chunking_strategy(strategy_name: str) -> ChunkingStrategy:
    """Get chunking strategy by name"""
    strategies = {
        'paragraph': ParagraphBasedChunking(),
        'sentence': SentenceBasedChunking(),
        'fixed': FixedSizeChunking(),
        'smart': SmartAdaptiveChunking()
    }
    
    return strategies.get(strategy_name, SmartAdaptiveChunking())

# Global instances
_text_chunker = None
_chunk_manager = None
_smart_processor = None

def get_text_chunker(max_chunk_size: int = 800, overlap: int = 100) -> TextChunker:
    """Get or create text chunker instance"""
    global _text_chunker
    if _text_chunker is None:
        _text_chunker = TextChunker(max_chunk_size, overlap)
    return _text_chunker

def get_chunk_manager() -> ChunkManager:
    """Get or create chunk manager instance"""
    global _chunk_manager
    if _chunk_manager is None:
        _chunk_manager = ChunkManager()
    return _chunk_manager

def get_smart_processor() -> SmartTextProcessor:
    """Get or create smart text processor instance"""
    global _smart_processor
    if _smart_processor is None:
        _smart_processor = SmartTextProcessor()
    return _smart_processor

# Test function
def test_chunking_system():
    """Test the chunking system"""
    print("=" * 60)
    print("Testing Chunking System")
    print("=" * 60)
    
    try:
        # Test text
        test_text = """
        Artificial Intelligence is transforming how we process information. 
        This is the first paragraph with some important content.
        
        Machine learning algorithms are becoming more sophisticated. 
        They can now understand complex patterns and make predictions.
        
        Natural language processing has seen remarkable advances. 
        Modern models can generate human-like text and understand context.
        
        Computer vision technologies are also advancing rapidly. 
        From medical imaging to autonomous vehicles, the applications are vast.
        
        The combination of these technologies creates powerful synergies. 
        AI systems that can both see and understand language open new possibilities.
        
        Ethical considerations are increasingly important. 
        As AI becomes more powerful, we must ensure it's developed responsibly.
        
        The future of AI is promising but requires careful stewardship. 
        With the right approach, AI can solve humanity's biggest challenges.
        """
        
        print("1. Testing different chunking strategies...")
        
        chunker = TextChunker(max_chunk_size=100, overlap=20)
        
        for strategy in ['paragraph', 'sentence', 'fixed', 'smart']:
            chunks = chunker.chunk_text(test_text, strategy)
            print(f"   {strategy.capitalize()}: {len(chunks)} chunks created")
            
            if chunks:
                avg_size = sum(c['word_count'] for c in chunks) // len(chunks)
                overlap_count = sum(1 for c in chunks if c['has_overlap'])
                print(f"     Avg size: {avg_size} words, Overlap chunks: {overlap_count}")
        
        print("\n2. Testing smart text processor...")
        processor = SmartTextProcessor()
        analysis = processor.analyze_text_structure(test_text)
        
        print(f"   Text analysis:")
        print(f"     Words: {analysis['word_count']}")
        print(f"     Sentences: {analysis['sentence_count']}")
        print(f"     Paragraphs: {analysis['paragraph_count']}")
        print(f"     Needs chunking: {analysis['needs_chunking']}")
        
        print("\n3. Testing chunk manager...")
        manager = ChunkManager()
        test_chunks = chunker.chunk_text(test_text, 'smart')
        manager.store_chunks(1, test_chunks)
        
        metadata = manager.get_chunk_metadata(1)
        print(f"   Stored chunks: {metadata.get('total_chunks', 0)}")
        print(f"   Total words: {metadata.get('total_words', 0)}")
        
        print("\n" + "=" * 60)
        print("✅ Chunking System Test PASSED")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Chunking System Test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_chunking_system()