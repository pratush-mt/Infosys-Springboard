# post_processing.py
import re
import string
from typing import List, Dict, Tuple, Optional
from collections import Counter
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import logging

logger = logging.getLogger(__name__)

class PostProcessor:
    """
    Task 12: Post-Processing and Summary Refinement
    Handles sentence reordering, duplicate removal, length constraints, and formatting enhancements.
    """
    
    def __init__(self):
        """Initialize the post-processor with NLP tools"""
        try:
            # Download required NLTK data
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            self.stop_words = set(stopwords.words('english'))
            self.nlp_available = True
        except Exception as e:
            logger.warning(f"NLTK initialization failed: {e}. Using fallback methods.")
            self.nlp_available = False
            self.stop_words = set()
    
    def split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences
        
        Args:
            text: Input text to split
            
        Returns:
            List of sentences
        """
        if not text or not text.strip():
            return []
        
        # Clean text first
        text = text.strip()
        
        if self.nlp_available:
            try:
                sentences = sent_tokenize(text)
                return [s.strip() for s in sentences if s.strip()]
            except Exception as e:
                logger.warning(f"NLTK sentence tokenization failed: {e}")
        
        # Fallback regex-based sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Handle edge cases
        if not sentences:
            # If no sentence endings found, treat as one sentence
            sentences = [text]
        
        return sentences
    
    def remove_duplicate_sentences(self, sentences: List[str]) -> List[str]:
        """
        Remove duplicate or highly similar sentences
        
        Args:
            sentences: List of input sentences
            
        Returns:
            List of unique sentences
        """
        if not sentences:
            return []
        
        seen = set()
        unique_sentences = []
        
        for sentence in sentences:
            # Create a normalized version for comparison
            normalized = self._normalize_sentence(sentence)
            
            # Check if we've seen this sentence before
            if normalized not in seen:
                seen.add(normalized)
                unique_sentences.append(sentence)
            else:
                logger.debug(f"Removed duplicate sentence: {sentence[:50]}...")
        
        return unique_sentences
    
    def _normalize_sentence(self, sentence: str) -> str:
        """
        Normalize a sentence for duplicate detection
        
        Args:
            sentence: Input sentence
            
        Returns:
            Normalized sentence string
        """
        # Convert to lowercase
        normalized = sentence.lower()
        
        # Remove punctuation
        normalized = normalized.translate(str.maketrans('', '', string.punctuation))
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove stop words for better similarity detection
        words = normalized.split()
        filtered_words = [w for w in words if w not in self.stop_words]
        
        return ' '.join(filtered_words)
    
    def reorder_sentences(self, sentences: List[str]) -> List[str]:
        """
        Reorder sentences to improve flow and readability
        
        Args:
            sentences: List of sentences
            
        Returns:
            Reordered sentences
        """
        if not sentences:
            return []
        
        if len(sentences) <= 1:
            return sentences
        
        # Score sentences based on position and content
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = self._calculate_sentence_score(sentence, i, len(sentences))
            scored_sentences.append((score, sentence))
        
        # Sort by score (higher scores come first for important sentences)
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Get reordered sentences
        reordered = [sentence for _, sentence in scored_sentences]
        
        # Ensure the first sentence is a good introduction
        first_sentence_idx = self._find_best_first_sentence(sentences)
        if first_sentence_idx != 0 and first_sentence_idx < len(reordered):
            best_first = reordered.pop(first_sentence_idx)
            reordered.insert(0, best_first)
        
        # Ensure the last sentence is a good conclusion
        last_sentence_idx = self._find_best_last_sentence(sentences)
        if last_sentence_idx != len(reordered) - 1 and last_sentence_idx < len(reordered):
            best_last = reordered.pop(last_sentence_idx)
            reordered.append(best_last)
        
        return reordered
    
    def _calculate_sentence_score(self, sentence: str, position: int, total_sentences: int) -> float:
        """
        Calculate a score for sentence importance
        
        Args:
            sentence: The sentence to score
            position: Position in original text (0-indexed)
            total_sentences: Total number of sentences
            
        Returns:
            Score (higher = more important)
        """
        score = 0.0
        
        # Position scoring (first and last sentences are often important)
        if position == 0:
            score += 2.0  # First sentence bonus
        elif position == total_sentences - 1:
            score += 1.5  # Last sentence bonus
        elif position < total_sentences * 0.2:  # First 20%
            score += 1.0
        elif position > total_sentences * 0.8:  # Last 20%
            score += 0.5
        
        # Length scoring (medium-length sentences often contain important info)
        word_count = len(sentence.split())
        if 10 <= word_count <= 25:
            score += 1.0
        elif word_count > 25:
            score += 0.5  # Very long sentences might be less readable
        
        # Content scoring
        # Check for important keywords or phrases
        important_keywords = ['however', 'therefore', 'thus', 'consequently', 
                            'important', 'significant', 'key', 'essential',
                            'conclusion', 'summary', 'result', 'finding']
        
        sentence_lower = sentence.lower()
        for keyword in important_keywords:
            if keyword in sentence_lower:
                score += 0.5
        
        # Check for numbers (often indicate facts)
        if re.search(r'\d+', sentence):
            score += 0.3
        
        return score
    
    def _find_best_first_sentence(self, sentences: List[str]) -> int:
        """
        Find the best sentence to start the summary
        
        Args:
            sentences: List of sentences
            
        Returns:
            Index of best first sentence
        """
        if not sentences:
            return 0
        
        best_idx = 0
        best_score = -1
        
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Shorter sentences often make better introductions
            word_count = len(sentence.split())
            if 8 <= word_count <= 20:
                score += 2
            
            # Check for introductory phrases
            intro_phrases = ['in summary', 'this article', 'the book', 'overall',
                           'generally', 'typically', 'usually', 'in general']
            
            sentence_lower = sentence.lower()
            for phrase in intro_phrases:
                if sentence_lower.startswith(phrase):
                    score += 3
                    break
            
            # Not starting with conjunctions is better
            if not sentence_lower.startswith(('and ', 'but ', 'or ', 'so ', 'however ', 'therefore ')):
                score += 1
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        return best_idx
    
    def _find_best_last_sentence(self, sentences: List[str]) -> int:
        """
        Find the best sentence to end the summary
        
        Args:
            sentences: List of sentences
            
        Returns:
            Index of best last sentence
        """
        if not sentences:
            return 0
        
        best_idx = len(sentences) - 1
        best_score = -1
        
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Check for concluding phrases
            concluding_phrases = ['in conclusion', 'to summarize', 'overall', 
                                'finally', 'ultimately', 'in summary', 
                                'the main point', 'the key takeaway']
            
            sentence_lower = sentence.lower()
            for phrase in concluding_phrases:
                if phrase in sentence_lower:
                    score += 3
                    break
            
            # Sentences that provide closure or final thoughts
            closure_words = ['therefore', 'thus', 'consequently', 'as a result',
                           'in summary', 'to conclude', 'finally']
            
            for word in closure_words:
                if word in sentence_lower:
                    score += 2
                    break
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        return best_idx
    
    def enforce_length_constraints(self, sentences: List[str], max_words: int = 150, 
                                   min_sentences: int = 3) -> List[str]:
        """
        Ensure summary meets length constraints
        
        Args:
            sentences: List of sentences
            max_words: Maximum allowed words
            min_sentences: Minimum number of sentences
            
        Returns:
            Filtered list of sentences meeting constraints
        """
        if not sentences:
            return []
        
        # Calculate total words
        total_words = sum(len(sentence.split()) for sentence in sentences)
        
        if total_words <= max_words and len(sentences) >= min_sentences:
            return sentences
        
        # If too short, try to add more content
        if total_words < max_words * 0.5 or len(sentences) < min_sentences:
            logger.warning("Summary is too short, but cannot add more content here")
            return sentences
        
        # If too long, remove less important sentences
        logger.info(f"Summary too long ({total_words} words). Reducing to {max_words} words.")
        
        # Score sentences by importance
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = self._calculate_sentence_score(sentence, i, len(sentences))
            word_count = len(sentence.split())
            scored_sentences.append((score, word_count, sentence))
        
        # Sort by score (descending)
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Select sentences until we reach max_words
        selected_sentences = []
        current_words = 0
        
        for score, word_count, sentence in scored_sentences:
            if current_words + word_count <= max_words:
                selected_sentences.append(sentence)
                current_words += word_count
            else:
                break
        
        # Ensure we have at least min_sentences
        if len(selected_sentences) < min_sentences:
            # Add highest scoring sentences until we reach min_sentences
            for score, word_count, sentence in scored_sentences[len(selected_sentences):]:
                if sentence not in selected_sentences:
                    selected_sentences.append(sentence)
                    if len(selected_sentences) >= min_sentences:
                        break
        
        # Reorder selected sentences to maintain some original flow
        selected_sentences = self._maintain_original_order(selected_sentences, sentences)
        
        logger.info(f"Reduced summary from {len(sentences)} to {len(selected_sentences)} sentences "
                   f"({total_words} to {current_words} words)")
        
        return selected_sentences
    
    def _maintain_original_order(self, selected_sentences: List[str], 
                                 original_sentences: List[str]) -> List[str]:
        """
        Maintain original order of selected sentences
        
        Args:
            selected_sentences: Sentences to reorder
            original_sentences: Original sentence order
            
        Returns:
            Sentences in original order
        """
        # Create a mapping of sentence to its position in original order
        sentence_positions = {}
        for i, sentence in enumerate(original_sentences):
            # Use normalized version for matching
            normalized = self._normalize_sentence(sentence)
            sentence_positions[normalized] = i
        
        # Sort selected sentences by their original position
        def get_position(sentence):
            normalized = self._normalize_sentence(sentence)
            return sentence_positions.get(normalized, float('inf'))
        
        return sorted(selected_sentences, key=get_position)
    
    def format_text(self, text: str) -> str:
        """
        Apply formatting enhancements to text
        
        Args:
            text: Input text
            
        Returns:
            Formatted text
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        # 1. Split into sentences first
        sentences = self.split_sentences(text)
        if not sentences:
            return text
        
        # 2. Capitalize first letter of each sentence
        formatted_sentences = []
        for sentence in sentences:
            if sentence:
                # Capitalize first letter
                if sentence[0].islower():
                    sentence = sentence[0].upper() + sentence[1:]
                
                # Ensure sentence ends with punctuation
                if not sentence.endswith(('.', '!', '?')):
                    sentence = sentence.rstrip() + '.'
                
                formatted_sentences.append(sentence)
        
        # 3. Join sentences with proper spacing
        formatted_text = ' '.join(formatted_sentences)
        
        # 4. Fix spacing around punctuation
        formatted_text = re.sub(r'\s+([.,!?])', r'\1', formatted_text)
        formatted_text = re.sub(r'([.,!?])(\w)', r'\1 \2', formatted_text)
        
        # 5. Remove excessive whitespace
        formatted_text = re.sub(r'\s+', ' ', formatted_text)
        
        # 6. Split into paragraphs if long
        if len(formatted_text.split()) > 100:
            formatted_text = self._add_paragraphs(formatted_text)
        
        return formatted_text.strip()
    
    def _add_paragraphs(self, text: str, sentences_per_paragraph: int = 3) -> str:
        """
        Add paragraph breaks to long text
        
        Args:
            text: Input text
            sentences_per_paragraph: Number of sentences per paragraph
            
        Returns:
            Text with paragraph breaks
        """
        sentences = self.split_sentences(text)
        
        paragraphs = []
        current_paragraph = []
        
        for i, sentence in enumerate(sentences):
            current_paragraph.append(sentence)
            
            # Start new paragraph after sentences_per_paragraph sentences
            # or at natural paragraph breaks
            if (i + 1) % sentences_per_paragraph == 0 or i == len(sentences) - 1:
                if current_paragraph:
                    paragraph_text = ' '.join(current_paragraph)
                    paragraphs.append(paragraph_text)
                    current_paragraph = []
        
        # Join paragraphs with double newline
        return '\n\n'.join(paragraphs)
    
    def process_summary(self, summary_text: str, max_words: int = 150, 
                       min_sentences: int = 3) -> Dict:
        """
        Complete post-processing pipeline for a summary
        
        Args:
            summary_text: Raw summary text
            max_words: Maximum word count
            min_sentences: Minimum number of sentences
            
        Returns:
            Dictionary with processed summary and metadata
        """
        logger.info(f"Starting post-processing for summary ({len(summary_text)} chars)")
        
        # Store original for comparison
        original_text = summary_text.strip()
        
        # Step 1: Split into sentences
        sentences = self.split_sentences(original_text)
        original_sentence_count = len(sentences)
        logger.info(f"Split into {original_sentence_count} sentences")
        
        # Step 2: Remove duplicate sentences
        unique_sentences = self.remove_duplicate_sentences(sentences)
        duplicate_removed = len(sentences) - len(unique_sentences)
        logger.info(f"Removed {duplicate_removed} duplicate sentences")
        
        # Step 3: Reorder sentences for better flow
        reordered_sentences = self.reorder_sentences(unique_sentences)
        
        # Step 4: Enforce length constraints
        constrained_sentences = self.enforce_length_constraints(
            reordered_sentences, max_words, min_sentences
        )
        
        # Step 5: Format the text
        intermediate_text = ' '.join(constrained_sentences)
        final_text = self.format_text(intermediate_text)
        
        # Calculate statistics
        final_sentences = self.split_sentences(final_text)
        
        stats = {
            'original_sentences': original_sentence_count,
            'final_sentences': len(final_sentences),
            'duplicates_removed': duplicate_removed,
            'original_length': len(original_text.split()),
            'final_length': len(final_text.split()),
            'reduction_percentage': round((1 - len(final_text.split()) / max(1, len(original_text.split()))) * 100, 1),
            'flow_improved': len(reordered_sentences) != len(unique_sentences),
            'formatting_applied': final_text != intermediate_text
        }
        
        logger.info(f"Post-processing complete. Final summary: {stats['final_sentences']} sentences, "
                   f"{stats['final_length']} words")
        
        return {
            'success': True,
            'processed_summary': final_text,
            'original_summary': original_text,
            'stats': stats,
            'processing_steps': [
                'Sentence splitting',
                'Duplicate removal',
                'Sentence reordering',
                'Length constraint enforcement',
                'Formatting enhancements'
            ]
        }


# Utility function to get post-processor instance
_post_processor_instance = None

def get_post_processor():
    """Get or create post-processor instance"""
    global _post_processor_instance
    if _post_processor_instance is None:
        _post_processor_instance = PostProcessor()
    return _post_processor_instance