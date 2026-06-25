"""
summary_postprocessor.py

Post-processing module for improving generated summaries.
Handles reordering, deduplication, length adjustment, and formatting.
"""

import re
import string
from typing import List, Tuple, Dict, Optional, Set, Union, Any
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import itertools
from heapq import nlargest

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('averaged_perceptron_tagger')

@dataclass
class SummaryConfig:
    """Configuration for summary post-processing."""
    max_words: Optional[int] = 200
    max_chars: Optional[int] = 1000
    min_words: Optional[int] = 50
    remove_duplicates: bool = True
    reorder_sentences: bool = True
    fix_punctuation: bool = True
    fix_capitalization: bool = True
    extract_keywords: bool = False
    num_keywords: int = 5
    paragraph_breaks: bool = True
    sentences_per_paragraph: int = 3
    target_compression_ratio: Optional[float] = None

class SummaryPostProcessor:
    """
    Post-processing functions to improve quality and readability of generated summaries.
    """
    
    def __init__(self, language: str = 'english', config: Optional[SummaryConfig] = None):
        """
        Initialize the post-processor.
        
        Args:
            language: Language for text processing (default: 'english')
            config: Configuration object for post-processing
        """
        self.language = language
        self.stop_words = set(stopwords.words(language))
        self.punctuation = set(string.punctuation)
        self.config = config or SummaryConfig()
        
    def process_summary(self, summary: str, reference_text: Optional[str] = None, 
                        original_length: Optional[int] = None) -> Dict[str, Any]:
        """
        Apply all post-processing steps to a summary.
        
        Args:
            summary: The summary text to process
            reference_text: Optional original text for context
            original_length: Original word count for compression calculation
            
        Returns:
            Dict containing processed summary and metadata
        """
        results = {
            'original_summary': summary,
            'original_length': len(word_tokenize(summary)),
            'processing_steps': []
        }
        
        # Step 1: Remove duplicates
        if self.config.remove_duplicates:
            summary, duplicates_removed = self.remove_duplicate_sentences(summary)
            results['duplicates_removed'] = duplicates_removed
            results['processing_steps'].append('duplicate_removal')
        
        # Step 2: Fix punctuation and capitalization
        if self.config.fix_punctuation:
            summary = self.fix_punctuation(summary)
            results['processing_steps'].append('punctuation_fix')
        
        if self.config.fix_capitalization:
            summary = self.fix_capitalization(summary)
            results['processing_steps'].append('capitalization_fix')
        
        # Step 3: Reorder sentences for logical flow
        if self.config.reorder_sentences:
            summary = self.reorder_sentences_logically(summary, reference_text)
            results['processing_steps'].append('sentence_reordering')
        
        # Step 4: Apply length constraints
        if self.config.max_words or self.config.target_compression_ratio:
            summary = self.enforce_length_constraints(
                summary, 
                max_words=self.config.max_words,
                target_compression_ratio=self.config.target_compression_ratio,
                original_length=original_length
            )
            results['processing_steps'].append('length_adjustment')
        
        # Step 5: Add paragraph breaks
        if self.config.paragraph_breaks:
            summary = self.add_paragraph_breaks(summary, self.config.sentences_per_paragraph)
            results['processing_steps'].append('paragraph_breaks')
        
        # Step 6: Extract keywords (optional)
        if self.config.extract_keywords:
            keywords = self.extract_keywords(summary, self.config.num_keywords)
            results['keywords'] = keywords
            results['processing_steps'].append('keyword_extraction')
        
        # Calculate final statistics
        results['processed_summary'] = summary
        results['processed_length'] = len(word_tokenize(summary))
        results['compression_ratio'] = results['processed_length'] / original_length if original_length else 0
        results['read_time_minutes'] = max(1, results['processed_length'] // 200)
        
        return results
    
    def reorder_sentences_logically(self, summary: str, reference_text: Optional[str] = None) -> str:
        """
        Reorder sentences to ensure logical flow and coherence.
        
        Args:
            summary: The summary text
            reference_text: Optional original text for context-based reordering
            
        Returns:
            Reordered summary
        """
        sentences = sent_tokenize(summary)
        
        if len(sentences) <= 1:
            return summary
        
        # If we have reference text, use semantic reordering
        if reference_text:
            return self._reorder_by_reference_similarity(sentences, reference_text)
        
        # Otherwise use topic modeling and coherence scoring
        return self._reorder_by_topic_coherence(sentences)
    
    def _reorder_by_reference_similarity(self, sentences: List[str], reference_text: str) -> str:
        """Reorder sentences based on similarity to reference text order."""
        reference_sentences = sent_tokenize(reference_text)
        
        if len(reference_sentences) == 0:
            return ' '.join(sentences)
        
        # Calculate similarity scores
        sentence_positions = []
        for sent in sentences:
            # Find the most similar reference sentence
            best_score = 0
            best_position = 0
            
            for i, ref_sent in enumerate(reference_sentences):
                similarity = self._calculate_sentence_similarity(sent, ref_sent)
                if similarity > best_score:
                    best_score = similarity
                    best_position = i
            
            sentence_positions.append((sent, best_position))
        
        # Sort by position in reference text
        sentence_positions.sort(key=lambda x: x[1])
        
        # Return reordered sentences
        return ' '.join([s[0] for s in sentence_positions])
    
    def _reorder_by_topic_coherence(self, sentences: List[str]) -> str:
        """Reorder sentences for better topical flow."""
        if len(sentences) <= 2:
            return ' '.join(sentences)
        
        # Extract topic words for each sentence
        sentence_topics = []
        for sentence in sentences:
            words = word_tokenize(sentence.lower())
            # Remove stopwords and punctuation
            content_words = [w for w in words if w not in self.stop_words and w not in self.punctuation]
            # Get most frequent content words as topics
            if content_words:
                word_freq = Counter(content_words)
                top_words = [word for word, _ in word_freq.most_common(3)]
                sentence_topics.append((sentence, top_words))
            else:
                sentence_topics.append((sentence, []))
        
        # Start with the sentence that has the most content words
        if sentence_topics:
            first_sentence = max(sentence_topics, key=lambda x: len(word_tokenize(x[0])))
            ordered = [first_sentence[0]]
            remaining = [s for s in sentences if s != first_sentence[0]]
            
            # Greedy algorithm to find next sentence with most topic overlap
            while remaining:
                last_sentence = ordered[-1]
                last_words = set(word_tokenize(last_sentence.lower()))
                last_words = [w for w in last_words if w not in self.stop_words and w not in self.punctuation]
                
                best_overlap = -1
                best_sentence = remaining[0]
                
                for sentence in remaining:
                    sentence_words = set(word_tokenize(sentence.lower()))
                    sentence_words = [w for w in sentence_words if w not in self.stop_words and w not in self.punctuation]
                    
                    overlap = len(set(last_words) & set(sentence_words))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_sentence = sentence
                
                ordered.append(best_sentence)
                remaining.remove(best_sentence)
            
            return ' '.join(ordered)
        
        return ' '.join(sentences)
    
    def _calculate_sentence_similarity(self, sentence1: str, sentence2: str) -> float:
        """Calculate similarity between two sentences."""
        words1 = set(word_tokenize(sentence1.lower()))
        words2 = set(word_tokenize(sentence2.lower()))
        
        # Remove stopwords and punctuation
        words1 = {w for w in words1 if w not in self.stop_words and w not in self.punctuation}
        words2 = {w for w in words2 if w not in self.stop_words and w not in self.punctuation}
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def remove_duplicate_sentences(self, text: str) -> Tuple[str, int]:
        """
        Remove duplicate or highly similar sentences from text.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (deduplicated_text, duplicates_removed_count)
        """
        sentences = sent_tokenize(text)
        
        if len(sentences) <= 1:
            return text, 0
        
        # Use a set to track seen sentences (normalized)
        seen_sentences = set()
        unique_sentences = []
        duplicates_removed = 0
        
        for sentence in sentences:
            # Normalize sentence for comparison
            normalized = self._normalize_sentence(sentence)
            
            # Check if similar sentence already seen
            is_duplicate = False
            for seen in seen_sentences:
                if self._are_sentences_similar(sentence, seen):
                    is_duplicate = True
                    duplicates_removed += 1
                    break
            
            if not is_duplicate:
                unique_sentences.append(sentence)
                seen_sentences.add(normalized)
        
        return ' '.join(unique_sentences), duplicates_removed
    
    def _normalize_sentence(self, sentence: str) -> str:
        """Normalize sentence for duplicate detection."""
        # Convert to lowercase, remove extra spaces and punctuation
        normalized = sentence.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        
        # Remove stopwords for better comparison
        words = normalized.split()
        words = [w for w in words if w not in self.stop_words]
        
        return ' '.join(words)
    
    def _are_sentences_similar(self, sent1: str, sent2: str, threshold: float = 0.8) -> bool:
        """
        Check if two sentences are similar above threshold.
        
        Args:
            sent1: First sentence
            sent2: Second sentence
            threshold: Similarity threshold (0-1)
            
        Returns:
            True if sentences are similar
        """
        norm1 = self._normalize_sentence(sent1)
        norm2 = self._normalize_sentence(sent2)
        
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return False
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union
        
        return similarity >= threshold
    
    def enforce_length_constraints(self, summary: str, max_words: Optional[int] = None, 
                                   max_chars: Optional[int] = None, 
                                   target_compression_ratio: Optional[float] = None,
                                   original_length: Optional[int] = None) -> str:
        """
        Adjust summary length to meet constraints.
        
        Args:
            summary: Summary text
            max_words: Maximum word count
            max_chars: Maximum character count
            target_compression_ratio: Target compression ratio
            original_length: Original text length in words
            
        Returns:
            Length-adjusted summary
        """
        sentences = sent_tokenize(summary)
        words = word_tokenize(summary)
        current_word_count = len(words)
        
        # Calculate target length
        target_words = None
        
        if target_compression_ratio and original_length:
            target_words = int(original_length * target_compression_ratio)
            target_words = max(self.config.min_words or 50, target_words)
        
        if max_words and (target_words is None or max_words < target_words):
            target_words = max_words
        
        # Apply character limit
        if max_chars and len(summary) > max_chars:
            summary = summary[:max_chars].rsplit(' ', 1)[0] + '...'
            sentences = sent_tokenize(summary)
            words = word_tokenize(summary)
            current_word_count = len(words)
        
        # If within limits, return as-is
        if target_words is None or current_word_count <= target_words:
            return summary
        
        # Need to trim summary
        if len(sentences) <= 1:
            # Single sentence - trim by removing less important words
            return self._trim_single_sentence(summary, target_words)
        
        # Multiple sentences - remove less important sentences
        return self._trim_multiple_sentences(sentences, target_words)
    
    def _trim_single_sentence(self, sentence: str, target_words: int) -> str:
        """Trim a single sentence to target word count."""
        words = word_tokenize(sentence)
        
        if len(words) <= target_words:
            return sentence
        
        # Keep the most important words (excluding stopwords)
        important_words = [w for w in words if w.lower() not in self.stop_words]
        
        if len(important_words) <= target_words:
            # Can't trim more without losing meaning
            return ' '.join(words[:target_words]) + '...'
        
        # Try to keep structure while trimming
        trimmed = []
        word_count = 0
        
        for word in words:
            if word_count >= target_words - 3:  # Leave room for "..."
                trimmed.append('...')
                break
            
            trimmed.append(word)
            if word not in string.punctuation:
                word_count += 1
        
        return ' '.join(trimmed)
    
    def _trim_multiple_sentences(self, sentences: List[str], target_words: int) -> str:
        """Trim multiple sentences by removing less important ones."""
        # Score sentences by importance
        sentence_scores = []
        for sentence in sentences:
            score = self._score_sentence_importance(sentence)
            sentence_scores.append((sentence, score, len(word_tokenize(sentence))))
        
        # Sort by importance (descending)
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select sentences until we reach target word count
        selected_sentences = []
        total_words = 0
        
        for sentence, score, word_count in sentence_scores:
            if total_words + word_count <= target_words or not selected_sentences:
                selected_sentences.append(sentence)
                total_words += word_count
            else:
                break
        
        # If we still have too many words, trim the last sentence
        if total_words > target_words and selected_sentences:
            last_sentence = selected_sentences[-1]
            words_to_remove = total_words - target_words
            last_sentence_words = word_tokenize(last_sentence)
            
            if len(last_sentence_words) > words_to_remove + 5:  # Keep at least 5 words
                trimmed_last = ' '.join(last_sentence_words[:len(last_sentence_words)-words_to_remove]) + '...'
                selected_sentences[-1] = trimmed_last
            else:
                # Remove the entire last sentence
                selected_sentences.pop()
        
        return ' '.join(selected_sentences)
    
    def _score_sentence_importance(self, sentence: str) -> float:
        """Score sentence importance based on various factors."""
        score = 0.0
        
        # Factor 1: Position (first sentences are often important)
        # (This factor is handled by the calling function)
        
        # Factor 2: Length (moderate length sentences are often more informative)
        words = word_tokenize(sentence)
        word_count = len(words)
        if 8 <= word_count <= 25:
            score += 0.3
        
        # Factor 3: Presence of keywords
        content_words = [w.lower() for w in words if w.lower() not in self.stop_words and w.lower() not in self.punctuation]
        if content_words:
            # Sentences with more unique content words are more important
            unique_words = len(set(content_words))
            score += unique_words / len(content_words) * 0.3
        
        # Factor 4: Sentence structure (questions and exclamations might be important)
        if sentence.strip().endswith('?'):
            score += 0.2
        elif sentence.strip().endswith('!'):
            score += 0.1
        
        return score
    
    def fix_punctuation(self, text: str) -> str:
        """
        Fix common punctuation issues.
        
        Args:
            text: Input text
            
        Returns:
            Text with corrected punctuation
        """
        if not text:
            return text
        
        # Fix missing spaces after punctuation
        text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
        
        # Fix multiple punctuation
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        
        # Fix missing spaces after commas
        text = re.sub(r',([A-Za-z])', r', \1', text)
        
        # Ensure proper spacing around parentheses
        text = re.sub(r'\(\s*', ' (', text)
        text = re.sub(r'\s*\)', ') ', text)
        
        # Fix quotes
        text = re.sub(r'\"\s*', '"', text)
        text = re.sub(r'\s*\"', '"', text)
        text = re.sub(r'\'\s*', "'", text)
        text = re.sub(r'\s*\'', "'", text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def fix_capitalization(self, text: str) -> str:
        """
        Fix capitalization issues.
        
        Args:
            text: Input text
            
        Returns:
            Text with proper capitalization
        """
        if not text:
            return text
        
        sentences = sent_tokenize(text)
        fixed_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Capitalize first letter
            if sentence[0].isalpha():
                sentence = sentence[0].upper() + sentence[1:]
            
            # Fix "i" to "I"
            sentence = re.sub(r'\bi\b', 'I', sentence)
            
            fixed_sentences.append(sentence)
        
        return ' '.join(fixed_sentences)
    
    def add_paragraph_breaks(self, text: str, sentences_per_paragraph: int = 3) -> str:
        """
        Add paragraph breaks to improve readability.
        
        Args:
            text: Input text
            sentences_per_paragraph: Number of sentences per paragraph
            
        Returns:
            Text with paragraph breaks
        """
        sentences = sent_tokenize(text)
        
        if len(sentences) <= sentences_per_paragraph:
            return text
        
        paragraphs = []
        current_paragraph = []
        
        for i, sentence in enumerate(sentences):
            current_paragraph.append(sentence)
            
            # Start new paragraph after specified number of sentences
            if len(current_paragraph) >= sentences_per_paragraph:
                # Also consider topic boundaries
                if i < len(sentences) - 1:
                    # Check if next sentence starts new topic
                    current_topic = self._extract_topic_keywords(' '.join(current_paragraph))
                    next_topic = self._extract_topic_keywords(sentences[i+1])
                    
                    topic_overlap = len(set(current_topic) & set(next_topic)) / max(len(set(current_topic)), 1)
                    
                    if topic_overlap < 0.3:  # Low topic overlap, good place for paragraph break
                        paragraphs.append(' '.join(current_paragraph))
                        current_paragraph = []
        
        # Add remaining sentences
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        return '\n\n'.join(paragraphs)
    
    def _extract_topic_keywords(self, text: str, num_keywords: int = 3) -> List[str]:
        """Extract topic keywords from text."""
        words = word_tokenize(text.lower())
        content_words = [w for w in words if w not in self.stop_words and w not in self.punctuation]
        
        if not content_words:
            return []
        
        word_freq = Counter(content_words)
        return [word for word, _ in word_freq.most_common(num_keywords)]
    
    def extract_keywords(self, text: str, num_keywords: int = 5) -> List[str]:
        """
        Extract main keywords from text.
        
        Args:
            text: Input text
            num_keywords: Number of keywords to extract
            
        Returns:
            List of keywords
        """
        words = word_tokenize(text.lower())
        
        # Remove stopwords and punctuation
        content_words = [w for w in words if w not in self.stop_words and w not in self.punctuation]
        
        if not content_words:
            return []
        
        # Calculate word frequencies
        word_freq = Counter(content_words)
        
        # Get most common words
        keywords = [word for word, count in word_freq.most_common(num_keywords * 2)]
        
        # Remove duplicates and very short words
        unique_keywords = []
        seen = set()
        for word in keywords:
            if len(word) > 2 and word not in seen:
                unique_keywords.append(word)
                seen.add(word)
            if len(unique_keywords) >= num_keywords:
                break
        
        return unique_keywords
    
    def identify_themes(self, text: str, num_themes: int = 3) -> List[str]:
        """
        Identify main themes in text.
        
        Args:
            text: Input text
            num_themes: Number of themes to identify
            
        Returns:
            List of themes
        """
        sentences = sent_tokenize(text)
        
        if not sentences:
            return []
        
        # Extract noun phrases as potential themes
        themes = []
        for sentence in sentences:
            words = word_tokenize(sentence)
            tagged = nltk.pos_tag(words)
            
            # Look for noun phrases (NN, NNS, NNP, NNPS)
            noun_phrases = []
            current_phrase = []
            
            for word, tag in tagged:
                if tag.startswith('NN'):  # Noun
                    current_phrase.append(word)
                elif current_phrase:
                    noun_phrases.append(' '.join(current_phrase))
                    current_phrase = []
            
            if current_phrase:
                noun_phrases.append(' '.join(current_phrase))
            
            themes.extend(noun_phrases)
        
        # Rank themes by frequency and length
        theme_counter = Counter(themes)
        ranked_themes = []
        
        for theme, count in theme_counter.most_common():
            if len(theme.split()) >= 2:  # Prefer multi-word phrases
                ranked_themes.append(theme)
            if len(ranked_themes) >= num_themes:
                break
        
        # If not enough multi-word themes, add single words
        if len(ranked_themes) < num_themes:
            single_words = [theme for theme, count in theme_counter.most_common() 
                           if len(theme.split()) == 1 and theme.lower() not in self.stop_words]
            ranked_themes.extend(single_words[:num_themes - len(ranked_themes)])
        
        return ranked_themes[:num_themes]

    def expand_summary(self, summary: str, target_words: int, 
                      reference_text: Optional[str] = None) -> str:
        """
        Expand a summary to reach target word count.
        
        Args:
            summary: Summary to expand
            target_words: Target word count
            reference_text: Original text for additional content
            
        Returns:
            Expanded summary
        """
        current_words = len(word_tokenize(summary))
        
        if current_words >= target_words:
            return summary
        
        if not reference_text:
            # Can't expand without reference text
            return summary
        
        # Extract additional sentences from reference text
        reference_sentences = sent_tokenize(reference_text)
        summary_sentences = set(sent_tokenize(summary))
        
        # Score reference sentences by relevance to summary
        scored_sentences = []
        for ref_sent in reference_sentences:
            if ref_sent in summary_sentences:
                continue
            
            # Calculate relevance score
            relevance = 0.0
            
            # Check overlap with summary keywords
            summary_keywords = self.extract_keywords(summary, 10)
            ref_keywords = self.extract_keywords(ref_sent, 10)
            
            if summary_keywords and ref_keywords:
                overlap = len(set(summary_keywords) & set(ref_keywords))
                relevance += overlap / len(summary_keywords)
            
            # Check position in original text (earlier sentences often more important)
            position_score = 1.0 - (reference_sentences.index(ref_sent) / len(reference_sentences))
            relevance += position_score * 0.3
            
            scored_sentences.append((ref_sent, relevance, len(word_tokenize(ref_sent))))
        
        # Sort by relevance
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Add sentences until we reach target word count
        expanded_summary = summary
        expanded_words = current_words
        
        for sentence, relevance, word_count in scored_sentences:
            if expanded_words + word_count <= target_words:
                expanded_summary += ' ' + sentence
                expanded_words += word_count
            else:
                # Try adding part of the sentence
                if word_count > 5:  # Only if sentence is long enough
                    words_to_add = target_words - expanded_words
                    if words_to_add >= 3:  # Add at least 3 words
                        sentence_words = word_tokenize(sentence)
                        partial_sentence = ' '.join(sentence_words[:words_to_add]) + '...'
                        expanded_summary += ' ' + partial_sentence
                        break
        
        return expanded_summary

    def format_for_display(self, text: str, style: str = 'paragraph') -> str:
        """
        Format summary for display based on style preference.
        
        Args:
            text: Summary text
            style: Display style ('paragraph' or 'bullet')
            
        Returns:
            Formatted summary
        """
        if style == 'bullet':
            sentences = sent_tokenize(text)
            formatted = '<ul class="summary-bullets">'
            for sentence in sentences:
                if sentence.strip():
                    formatted += f'<li>{sentence.strip()}</li>'
            formatted += '</ul>'
            return formatted
        else:
            # Paragraph style with proper HTML formatting
            text = text.replace('\n\n', '</p><p>')
            text = text.replace('\n', '<br>')
            return f'<p>{text}</p>'