import logging
import re
from typing import Any, Dict, List, Set

import nltk
from nltk import ne_chunk, pos_tag, word_tokenize
from nltk.chunk import RegexpParser
from nltk.corpus import stopwords
from textblob import TextBlob

# Download required NLTK data
try:
    nltk.data.find("tokenizers/punkt")
    nltk.data.find("taggers/averaged_perceptron_tagger")
    nltk.data.find("chunkers/maxent_ne_chunker")
    nltk.data.find("corpora/words")
except LookupError:
    nltk.download("punkt")
    nltk.download("averaged_perceptron_tagger")
    nltk.download("maxent_ne_chunker")
    nltk.download("words")
    nltk.download("stopwords")

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes content for readability, keywords, and other metrics."""

    REQUIRED_FIELDS = ["content", "llm_analysis"]
    WORDS_PER_MINUTE = 200  # Average reading speed

    # Custom grammar for technical terms
    GRAMMAR = r"""
        VERSION: {<CD>(<.\w*>)?<CD>?}     # Version numbers like "2.0"
        TECH_TERM: {<NN.*>+(<HYPH>?<CD>*|<VERSION>|<CD>)}  # Terms like "GPT-4", "Python3"
        VERSIONED_TERM: {<NN.*>+<VERSION>}  # Terms like "PyTorch 2.0"
        NP: {<JJ.*>*<NN.*>+}              # Noun phrases with optional adjectives
        TECH_NP: {<NP>(<IN><NP>)+}        # Technical phrases with prepositions
        ML_TERM: {<NN.*><NN.*>}           # Common two-word technical terms
    """

    # Common technical phrases to preserve
    TECH_PHRASES = [
        r"principle of least privilege",
        r"state of the art",
        r"quality of service",
        r"machine learning",
        r"deep learning",
        r"natural language processing",
        r"artificial intelligence",
        r"neural networks?",
        r"computer vision",
        r"data science",
        r"pattern recognition",
        r"internet of things",
        r"cloud computing",
        r"distributed systems",
        r"information security",
        r"software engineering",
        r"theory of computation",
        r"operating systems?",
        r"database systems?",
        r"machine translation",
        r"knowledge representation",
        r"information retrieval",
        r"computer graphics",
        r"parallel computing",
        r"quantum computing",
        r"edge computing",
        r"blockchain technology",
        r"cyber security",
        r"data mining",
        r"big data",
        r"DevOps",
        r"continuous integration",
        r"continuous deployment",
        r"version control",
        r"code review",
        r"test driven development",
        r"agile development",
        r"microservices architecture",
        r"containerization",
        r"virtualization",
        r"load balancing",
        r"fault tolerance",
        r"high availability",
        r"scalability",
        r"performance optimization",
    ]

    def __init__(self):
        """Initialize the analyzer with custom chunker."""
        self.chunk_parser = RegexpParser(self.GRAMMAR)
        self.stop_words = set(stopwords.words("english"))

    def _extract_entities(self, text: str) -> Set[str]:
        """Extract named entities from text using NLTK.

        Args:
            text: Text to analyze

        Returns:
            Set of named entities
        """
        tokens = word_tokenize(text)
        pos_tags = pos_tag(tokens)
        named_entities = ne_chunk(pos_tags)

        entities = set()
        for chunk in named_entities:
            if hasattr(chunk, "label"):
                entity = " ".join(c[0] for c in chunk.leaves())
                entities.add(entity)
        return entities

    def _extract_technical_terms(self, text: str) -> Set[str]:
        """Extract technical terms using custom grammar rules.

        Args:
            text: Text to analyze

        Returns:
            Set of technical terms
        """
        tokens = word_tokenize(text)
        pos_tags = pos_tag(tokens)
        chunks = self.chunk_parser.parse(pos_tags)

        terms = set()
        for chunk in chunks:
            if hasattr(chunk, "label"):
                if chunk.label() in (
                    "TECH_TERM",
                    "VERSIONED_TERM",
                    "NP",
                    "TECH_NP",
                    "ML_TERM",
                ):
                    term = " ".join(c[0] for c in chunk.leaves())
                    # Filter out terms that are just stopwords
                    term_words = set(term.lower().split())
                    if not term_words.issubset(self.stop_words):
                        # Special handling for version numbers
                        if chunk.label() in ("TECH_TERM", "VERSIONED_TERM") and any(
                            c[1].startswith("CD") for c in chunk.leaves()
                        ):
                            terms.add(
                                term
                            )  # Preserve original case for versioned terms
                        # Special handling for multi-word technical terms
                        elif len(term.split()) > 1:
                            terms.add(term.lower())
                            # Add common variations
                            if chunk.label() == "ML_TERM":
                                terms.add(term.lower())
                        else:
                            terms.add(term.lower())
        return terms

    def _normalize_technical_phrases(self, text: str) -> Set[str]:
        """Extract and normalize complex technical phrases.

        Args:
            text: Text to analyze

        Returns:
            Set of normalized phrases
        """
        phrases = set()
        text_lower = text.lower()

        # Find all technical phrases
        for pattern in self.TECH_PHRASES:
            matches = re.finditer(pattern, text_lower)
            phrases.update(match.group(0) for match in matches)

        return phrases

    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text using multiple methods.

        Args:
            text: Text to analyze

        Returns:
            List of keywords
        """
        keywords = set()

        # Extract named entities
        keywords.update(self._extract_entities(text))

        # Extract technical terms using custom grammar
        keywords.update(self._extract_technical_terms(text))

        # Extract common technical phrases
        keywords.update(self._normalize_technical_phrases(text))

        # Use TextBlob as fallback for additional noun phrases
        blob = TextBlob(text)
        keywords.update(blob.noun_phrases)

        # Add individual nouns and proper nouns from TextBlob
        for word, tag in blob.tags:
            if tag.startswith("NN"):  # Noun tags: NN, NNS, NNP, NNPS
                # Preserve case for proper nouns, acronyms, and technical terms
                if (
                    tag == "NNP"
                    or (len(word) <= 5 and word.isupper())  # Proper nouns
                    or any(word.lower().endswith(str(i)) for i in range(10))  # Acronyms
                    or word in text  # Version numbers
                ):  # Preserve original case if exact match found
                    keywords.add(word)
                else:
                    keywords.add(word.lower())

        # Clean and normalize keywords
        cleaned = set()
        for keyword in keywords:
            # Remove special characters and normalize whitespace
            clean = re.sub(
                r"[^a-zA-Z0-9\s\-\.]", "", keyword
            ).strip()  # Allow dots for versions
            if clean and len(clean) > 2:  # Skip very short keywords
                # Preserve case for special terms and technical phrases
                if any(
                    [
                        re.search(r"[A-Z]-\d|[A-Z]{2,}", clean),  # GPT-4, AI, etc.
                        re.search(r"\d", clean),  # Python3, PyTorch 2.0, etc.
                        len(clean.split()) > 1,  # Multi-word technical terms
                        clean.isupper(),  # Acronyms
                    ]
                ):
                    cleaned.add(clean)
                else:
                    cleaned.add(clean.lower())

        return sorted(cleaned)

    def analyze_readability(self, text: str) -> Dict[str, float]:
        """Calculate readability metrics.

        Args:
            text: Text to analyze

        Returns:
            Dictionary of readability metrics
        """
        if not text.strip():
            return {
                "flesch_score": 0.0,
                "avg_sentence_length": 0.0,
                "avg_word_length": 0.0,
            }

        blob = TextBlob(text)
        sentences = blob.sentences
        words = blob.words

        # Calculate metrics
        word_count = len(words)
        sentence_count = len(sentences)
        syllable_count = sum(self._count_syllables(word) for word in words)

        # Avoid division by zero
        if sentence_count == 0 or word_count == 0:
            return {
                "flesch_score": 0.0,
                "avg_sentence_length": 0.0,
                "avg_word_length": 0.0,
            }

        # Calculate Flesch Reading Ease score
        avg_sentence_length = word_count / sentence_count
        avg_syllables_per_word = syllable_count / word_count
        flesch_score = (
            206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        )

        # Calculate average word length
        avg_word_length = sum(len(word) for word in words) / word_count

        return {
            "flesch_score": max(0.0, min(100.0, flesch_score)),
            "avg_sentence_length": avg_sentence_length,
            "avg_word_length": avg_word_length,
        }

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word using a basic heuristic."""
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        prev_char_is_vowel = False

        # Handle special cases
        if word.endswith("e"):
            word = word[:-1]
        if word.endswith("ed"):
            word = word[:-2]
        if word.endswith("es"):
            word = word[:-2]

        # Count vowel groups
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_char_is_vowel:
                count += 1
            prev_char_is_vowel = is_vowel

        # Ensure at least one syllable
        return max(1, count)

    def analyze_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a feed item.

        Args:
            item: Feed item to analyze

        Returns:
            Analysis results including keywords, readability metrics, etc.

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            if field not in item:
                raise ValueError(f"Missing required field: {field}")

        # Get content
        content = item["content"]
        if isinstance(content, dict):
            content = content.get("content", "")

        # Create TextBlob for analysis
        blob = TextBlob(content)

        # Calculate word and sentence counts
        word_count = len(blob.words)
        sentence_count = len(blob.sentences)

        # Calculate reading time
        reading_time = word_count / self.WORDS_PER_MINUTE

        # Extract keywords from content only
        keywords = self.extract_keywords(content) if content.strip() else []

        # Analyze readability
        readability = self.analyze_readability(content)

        return {
            "keywords": keywords,
            "readability": readability,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "reading_time_minutes": reading_time,
        }

    def batch_analyze(
        self, items: List[Dict[str, Any]], batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Analyze multiple feed items.

        Args:
            items: List of feed items to analyze
            batch_size: Number of items to process in parallel (not implemented yet)

        Returns:
            List of analysis results
        """
        results = []
        for item in items:
            try:
                result = self.analyze_item(item)
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing item: {str(e)}")
                # Continue processing remaining items
                continue

        return results
